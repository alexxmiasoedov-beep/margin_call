"""s293 — часовые метрики data.binance.vision (OI, лонг/шорт топ-трейдеров и всех счетов, taker) для первого периода
10.2020–09.2022: в архиве они есть только с 01.12.2021, поэтому берётся отрезок 01.12.2021–30.09.2022 (10 мес.).
Тот же разбор, что `research/s230/fetch_metrics.py` (колонки: время, OI в монетах, OI $, топ по счетам, топ по позициям,
все счета, taker; только минута 00). Монеты — из `s117/k_2020.pkl`. Итог — `s293/metrics_2021/<монета>.npy`.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s293/fetch_metrics_2021.py"""
import datetime
import importlib.util
import json
import os
import pickle
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("fm", os.path.join(HERE, "..", "s230", "fetch_metrics.py"))
FM = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FM)
UTC = datetime.timezone.utc
DAY = 86400
D0 = datetime.datetime(2021, 12, 1, tzinfo=UTC).timestamp()
D1 = datetime.datetime(2022, 9, 30, tzinfo=UTC).timestamp()
OUT = "s293/metrics_2021"
THREADS = int(os.environ.get("THREADS", "8"))


def main():
    K = pickle.load(open("s117/k_2020.pkl", "rb"))
    os.makedirs(OUT, exist_ok=True)
    vol = {s: float(np.nansum(a["qv"])) for s, a in K.items()}
    order = sorted(vol, key=vol.get, reverse=True)
    miss = {}
    t0 = time.time(); n_req = 0
    for i, s in enumerate(order):
        path = f"{OUT}/{s}.npy"
        if os.path.exists(path):
            continue
        t = K[s]["t"]
        lo = max(D0, float(t[0]) // DAY * DAY); hi = min(D1, float(t[-1]) // DAY * DAY)
        if hi < lo:
            np.save(path, np.zeros((0, 7)))
            continue
        days = [datetime.datetime.fromtimestamp(d, UTC).strftime("%Y-%m-%d") for d in np.arange(lo, hi + DAY, DAY)]
        with ThreadPoolExecutor(THREADS) as ex:
            got = list(ex.map(lambda d: FM.day_rows(s, d), days))
        n_req += len(days)
        bad = [d for d, g in zip(days, got) if g is None]
        rows = [r for g in got if g for r in g]
        np.save(path, np.array(sorted(rows)) if rows else np.zeros((0, 7)))
        if bad:
            miss[s] = bad
            json.dump(miss, open("s293/miss_2021.json", "w"))
        print(f"{i + 1}/{len(order)} {s}: дней {len(days)}, строк {len(rows)}, сбоев {len(bad)}; "
              f"{n_req} запросов за {(time.time() - t0) / 60:.0f} мин", flush=True)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
