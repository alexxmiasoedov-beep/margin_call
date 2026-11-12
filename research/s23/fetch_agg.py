"""Посекундный путь цены вокруг начисления фандинга по ленте сделок (aggTrades, data.binance.vision, дневные архивы).
Выборка — до 250 начислений с прошлой ставкой ≤ −1% и до 250 с прошлой ставкой от −1% до −0,3% (не больше 3 на монету,
равномерно по времени). Из дневного архива берутся сделки за [T − 60 с, T + 180 с]; кэш s23/agg/{монета}_{T}.npy:
[время мс, цена, объём, покупатель-мейкер]. Запуск из папки с данными."""
import io
import os
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

D = "s23/agg"; os.makedirs(D, exist_ok=True)
BASE = "https://data.binance.vision/data/futures/um/daily/aggTrades"


def one(r):
    s, T = r
    fn = f"{D}/{s}_{T}.npy"
    if os.path.exists(fn):
        return 1
    day = pd.Timestamp(T, unit="s").strftime("%Y-%m-%d")
    url = f"{BASE}/{s}USDT/{s}USDT-aggTrades-{day}.zip"
    for i in range(3):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                z = zipfile.ZipFile(io.BytesIO(resp.read()))
            lo, hi = (T - 60) * 1000, (T + 180) * 1000
            out = []
            with z.open(z.namelist()[0]) as f:
                for ln in io.TextIOWrapper(f):
                    p = ln.split(",")
                    if not p[0][:1].isdigit():
                        continue
                    ts = int(p[5])
                    if ts < lo:
                        continue
                    if ts > hi:
                        break
                    out.append((ts, float(p[1]), float(p[2]), 1.0 if p[6].strip().lower() == "true" else 0.0))
            np.save(fn, np.array(out) if out else np.zeros((0, 4)))
            return 1
        except urllib.error.HTTPError as e:
            if e.code == 404:
                np.save(fn, np.zeros((0, 4)))
                return 0
        except Exception:
            pass
        time.sleep(3 + 3 * i)
    return 0


if __name__ == "__main__":
    E = pd.read_pickle("s23/fund_events.pkl")
    E = E[E["T"] % 86400 != 0]                   # начисление в 00:00 — день архива другой; для простоты без них
    pick = []
    for lo, hi in ((-1.0, -0.01), (-0.01, -0.003)):
        g = E[(E.prev > lo) & (E.prev <= hi)].sort_values("T")
        keep = []
        for _, d in g.groupby("s"):
            keep += list(d.index[np.linspace(0, len(d) - 1, min(3, len(d))).astype(int)])
        g = g.loc[sorted(set(keep))].sort_values("T")
        g = g.iloc[np.linspace(0, len(g) - 1, min(250, len(g))).astype(int)]
        pick += list(zip(g.s, g["T"].astype(int)))
    print(f"событий в выборке {len(pick)}", flush=True)
    t0 = time.time(); n = 0
    with ThreadPoolExecutor(12) as ex:
        for i, ok in enumerate(ex.map(one, pick)):
            n += ok
            if i % 50 == 0:
                print(f"  {i}/{len(pick)} ({n}), {time.time() - t0:.0f} с", flush=True)
    print(f"готово: {n} из {len(pick)}, {time.time() - t0:.0f} с")
