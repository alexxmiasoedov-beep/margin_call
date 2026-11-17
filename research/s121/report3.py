"""s121 — сводка по трём периодам (после newlist3.py в ~/mc_2020, ~/mc_oos, ~/mc_data). t — с кластерами по дням входа."""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import ct  # noqa: E402

P = {"2020–2022": "/home/user/mc_2020/s121_2020.pkl", "2022–2024": "/home/user/mc_oos/s121_2022.pkl", "2024–2026": "/home/user/mc_data/s121_2024.pkl"}
P = {k: pd.read_pickle(v) for k, v in P.items()}
for nm in ("30/30/14", "7 сут/стоп 50"):
    cells, allx = [], []
    for k, X in P.items():
        x = X[X[nm].notna()]
        m, t, n = ct(x[nm], x.t)
        cells.append(f"{k}: n={n} {m:+.2%} (t {t:+.1f})")
        allx.append(x)
    a = pd.concat(allx); m, t, n = ct(a[nm], a.t)
    print(f"{nm:14s} | " + " | ".join(cells) + f" | 6 лет: n={n} {m:+.2%} (t {t:+.1f}), в плюсе {(a[nm] > 0).mean():.0%}")
