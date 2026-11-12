"""Г12: полные 5-мин метрики data.binance.vision (OI, лонг/шорт топ-трейдеров по счетам и по позициям, лонг/шорт всех
счетов, taker buy/sell) по 100 самым торгуемым перпам за период свечей. Хранятся почасовые отметки (минута 00):
s22/metrics_full/<символ>/<день>.npy, колонки: время, OI в монетах, OI $, топ по счетам, топ по позициям, все счета,
taker. Запуск из папки с данными: python3 .../s22/h12_fetch.py"""
import datetime
import io
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import DAY, K, NONCRYPTO, UTC, live


def full_day(sym, day):
    path = f"s22/metrics_full/{sym}/{day}.npy"
    if os.path.exists(path):
        return np.load(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    url = f"https://data.binance.vision/data/futures/um/daily/metrics/{sym}USDT/{sym}USDT-metrics-{day}.zip"
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            rows = []
            for ln in z.read(z.namelist()[0]).decode().splitlines()[1:]:
                p = ln.split(",")
                if len(p) >= 8 and p[0].endswith(":00:00"):
                    t = datetime.datetime.strptime(p[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
                    rows.append([t] + [float(x) if x else np.nan for x in p[2:8]])
            arr = np.array(rows) if rows else np.zeros((0, 7))
            np.save(path, arr)
            return arr
        except urllib.error.HTTPError as e:
            if e.code == 404:
                arr = np.zeros((0, 7)); np.save(path, arr); return arr
        except Exception:
            time.sleep(2)
    return np.zeros((0, 7))                                          # сбой сети — не кэшируем


if __name__ == "__main__":
    vol = {s: float(a["qv"].sum()) for s, a in K.items() if s not in NONCRYPTO}
    top = sorted(vol, key=vol.get, reverse=True)[:100]
    open("s22/top100.txt", "w").write("\n".join(top))
    need = []
    for s in top:
        lo, hi = live(s)
        for d in np.arange(lo // DAY * DAY, hi + DAY, DAY):
            need.append((s, datetime.datetime.fromtimestamp(d, UTC).strftime("%Y-%m-%d")))
    print(f"монет 100, дней метрик {len(need)}", flush=True)
    t0 = time.time(); done = [0]

    def get(x):
        a = full_day(*x); done[0] += 1
        if done[0] % 5000 == 0:
            print(f"  {done[0]}/{len(need)} за {(time.time() - t0) / 60:.0f} мин", flush=True)
        return len(a)
    with ThreadPoolExecutor(24) as ex:
        n = list(ex.map(get, need))
    print(f"готово: с данными {sum(1 for x in n if x)}, пустых {sum(1 for x in n if not x)}, {(time.time() - t0) / 60:.0f} мин")
