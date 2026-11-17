"""s128 — сводка по трём периодам."""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import ct  # noqa: E402

P = {"2020–2022": "/home/user/mc_2020/s128_2020.pkl", "2022–2024": "/home/user/mc_oos/s128_2022.pkl", "2024–2026": "/home/user/mc_data/s128_2024.pkl"}
P = {k: pd.read_pickle(v) for k, v in P.items()}
for lab, f in (("ставка ≥ +0,01% (основная)", lambda x: x.rate >= 0.0001), ("между", lambda x: (x.rate > -0.0001) & (x.rate < 0.0001)),
               ("ставка ≤ −0,01%", lambda x: x.rate <= -0.0001)):
    cells, allx = [], []
    for k, X in P.items():
        x = X[f(X)]; months = (X.t.max() - X.t.min()) / (30.4 * 86400)
        m, t, n = ct(x.net, x.t)
        cells.append(f"{k}: n={n} ({n / months:.1f}/мес) {m:+.2%} (t {t:+.1f})")
        allx.append(x)
    a = pd.concat(allx); m, t, n = ct(a.net, a.t)
    print(f"{lab:28s} | " + " | ".join(cells) + f" | 6 лет: {m:+.2%} (t {t:+.1f})")
