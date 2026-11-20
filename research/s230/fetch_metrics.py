"""s230 — часовые метрики data.binance.vision (OI, лонг/шорт топ-трейдеров по счетам и позициям, всех счетов, taker) для
перпов независимой выборки s117 (10.2022–09.2024, 327 монет) с запасом 31 сут для окон «относительно своей истории».
Колонки как в s22/metrics_full: время, OI в монетах, OI $, топ по счетам, топ по позициям, все счета, taker; только
отметки минуты 00. Итог — один файл на монету: s230/metrics/<монета>.npy (float64), пропуски сети — s230/miss.json.
Метрики в архиве есть с 01.12.2021. Монеты — по убыванию оборота, готовые пропускаются; дни со сбоем сети
(miss.json) докачиваются при следующем запуске. Потоков — THREADS (по умолчанию 8: при 16 и параллельной загрузке
другого исследования до 15% запросов падало).
Запуск из /home/user/mc_data: python3 <repo>/research/s230/fetch_metrics.py"""
import datetime
import io
import json
import os
import pickle
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np

UTC = datetime.timezone.utc
DAY = 86400
D0 = datetime.datetime(2022, 8, 31, tzinfo=UTC).timestamp()
D1 = datetime.datetime(2024, 9, 30, tzinfo=UTC).timestamp()
OUT = "s230/metrics"
UA = {"User-Agent": "research-script/1.0"}
THREADS = int(os.environ.get("THREADS", "8"))


def day_rows(sym, day):
    """Строки минуты 00 за день; [] — дня нет в архиве (404); None — сбой сети."""
    url = f"https://data.binance.vision/data/futures/um/daily/metrics/{sym}USDT/{sym}USDT-metrics-{day}.zip"
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            rows = []
            for ln in z.read(z.namelist()[0]).decode().splitlines()[1:]:
                p = ln.split(",")
                if len(p) >= 8 and p[0].endswith(":00:00"):
                    t = datetime.datetime.strptime(p[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
                    rows.append([t] + [float(x.strip('"')) if x.strip('"') else np.nan for x in p[2:8]])   # пустые поля бывают «""»
            return rows
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            time.sleep(2 * (k + 1))
        except Exception:
            time.sleep(2 * (k + 1))
    return None


def main():
    K = pickle.load(open("s117/k_oos.pkl", "rb"))
    os.makedirs(OUT, exist_ok=True)
    vol = {s: float(np.nansum(a["qv"])) for s, a in K.items()}
    order = sorted(vol, key=vol.get, reverse=True)
    miss = json.load(open("s230/miss.json")) if os.path.exists("s230/miss.json") else {}
    t0 = time.time(); n_req = 0
    for s in [x for x in order if miss.get(x) and os.path.exists(f"{OUT}/{x}.npy")]:   # докачка дней со сбоем
        with ThreadPoolExecutor(THREADS) as ex:
            got = list(ex.map(lambda d: day_rows(s, d), miss[s]))
        n_req += len(miss[s])
        old = np.load(f"{OUT}/{s}.npy")
        rows = [list(r) for r in old] + [r for g in got if g for r in g]
        np.save(f"{OUT}/{s}.npy", np.array(sorted(rows)) if rows else np.zeros((0, 7)))
        miss[s] = [d for d, g in zip(miss[s], got) if g is None]
        json.dump(miss, open("s230/miss.json", "w"))
        print(f"докачка {s}: осталось сбоев {len(miss[s])}", flush=True)
    for i, s in enumerate(order):
        path = f"{OUT}/{s}.npy"
        if os.path.exists(path):
            continue
        t = K[s]["t"]
        lo = max(D0, float(t[0]) // DAY * DAY - 31 * DAY); hi = min(D1, float(t[-1]) // DAY * DAY)
        days = [datetime.datetime.fromtimestamp(d, UTC).strftime("%Y-%m-%d") for d in np.arange(lo, hi + DAY, DAY)]
        with ThreadPoolExecutor(THREADS) as ex:
            got = list(ex.map(lambda d: day_rows(s, d), days))
        n_req += len(days)
        bad = [d for d, g in zip(days, got) if g is None]
        rows = [r for g in got if g for r in g]
        arr = np.array(sorted(rows)) if rows else np.zeros((0, 7))
        np.save(path, arr)
        if bad:
            miss[s] = bad
            json.dump(miss, open("s230/miss.json", "w"))
        print(f"{i + 1}/{len(order)} {s}: дней {len(days)}, строк {len(arr)}, сбоев {len(bad)}; "
              f"{n_req} запросов за {(time.time() - t0) / 60:.0f} мин", flush=True)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
