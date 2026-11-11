"""Г1 (д): события «цена фьючерса за 4 ч +5% и больше» по всем 869 фьючерсам (одно на монету за сутки, свечи с объёмом,
фьючерс старше суток) и докачка 5-мин метрик OI за дни T и T − 4 ч (data.binance.vision, кэш s20/metrics).
Сохраняет s22/oi_events.pkl. Запуск из папки с данными: python3 .../s22/oi_fetch.py"""
import datetime
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import DAY, GR, H, K, UTC, live, metrics_day, thin

if __name__ == "__main__":
    g, C = GR["grid"], GR["C"]; rows = []
    for s in K:
        c = C[GR["row"][s]]; lo, hi = live(s)
        k = np.arange(4, len(g)); r4 = c[k] / c[k - 4] - 1
        ok = np.isfinite(r4) & (r4 >= 0.05) & (g[k] - 900 >= lo + DAY) & (g[k] <= hi)
        rows += [dict(s=s, T=int(g[i]), r4=float(c[i] / c[i - 4] - 1)) for i in k[ok]]
    E = thin(pd.DataFrame(rows).sort_values("T"))
    E.to_pickle("s22/oi_events.pkl")
    need = sorted({(s, datetime.datetime.fromtimestamp(t - 1, UTC).strftime("%Y-%m-%d")) for s, T in zip(E.s, E["T"])
                   for t in (T, T - 4 * H)})
    print(f"событий {len(E)}, дней метрик {len(need)}", flush=True)
    t0 = time.time(); done = [0]

    def get(x):
        a = metrics_day(*x); done[0] += 1
        if done[0] % 2000 == 0:
            print(f"  {done[0]}/{len(need)} за {(time.time() - t0) / 60:.0f} мин", flush=True)
        return len(a)
    with ThreadPoolExecutor(24) as ex:
        n = list(ex.map(get, need))
    print(f"готово: с данными {sum(1 for x in n if x)}, пустых {sum(1 for x in n if not x)}, {(time.time() - t0) / 60:.0f} мин")
