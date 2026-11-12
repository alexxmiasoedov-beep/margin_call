"""Минутные свечи фьючерсов (data.binance.vision, дневные архивы) для дней начислений с прошлой ставкой ≤ −0,3%
(s23/fund_events.pkl) и предыдущих дней (для входа до начисления в 00:00). Кэш — s23/k1m/{SYM}_{date}.npy:
[время открытия, open, high, low, close, оборот $, агрессивные покупки $]. Запуск из папки с данными."""
import io
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

TH = float(sys.argv[1]) if len(sys.argv) > 1 else -0.003
D = "s23/k1m"; os.makedirs(D, exist_ok=True)
BASE = "https://data.binance.vision/data/futures/um/daily/klines"


def one(sd):
    s, day = sd
    fn = f"{D}/{s}_{day}.npy"
    if os.path.exists(fn):
        return 1
    url = f"{BASE}/{s}USDT/1m/{s}USDT-1m-{day}.zip"
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            rows = []
            for ln in z.read(z.namelist()[0]).decode().splitlines():
                p = ln.split(",")
                if p and p[0][:1].isdigit():
                    rows.append((int(p[0]) // 1000, float(p[1]), float(p[2]), float(p[3]), float(p[4]), float(p[7]), float(p[10])))
            np.save(fn, np.array(rows))
            return 1
        except urllib.error.HTTPError as e:
            if e.code == 404:
                np.save(fn, np.zeros((0, 7)))
                return 0
        except Exception:
            pass
        time.sleep(2 + 3 * i)
    return 0


if __name__ == "__main__":
    E = pd.read_pickle("s23/fund_events.pkl")
    E = E[E.prev <= TH]
    days = set()
    for s, T in zip(E.s, E["T"]):
        d = pd.Timestamp(T, unit="s")
        days.add((s, d.strftime("%Y-%m-%d")))
        if d.hour < 3:
            days.add((s, (d - pd.Timedelta(days=1)).strftime("%Y-%m-%d")))
    days = sorted(days)
    print(f"событий {len(E)}, дней-монет {len(days)}", flush=True)
    t0 = time.time(); n = 0
    with ThreadPoolExecutor(16) as ex:
        for i, ok in enumerate(ex.map(one, days)):
            n += ok
            if i % 1000 == 0:
                print(f"  {i}/{len(days)} ({n} с данными), {time.time() - t0:.0f} с", flush=True)
    print(f"готово: {n} из {len(days)}, {time.time() - t0:.0f} с")
