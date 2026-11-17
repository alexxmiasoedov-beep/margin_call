"""s129 — сводка по трём периодам."""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import ct  # noqa: E402

P = {"2020–2022": "/home/user/mc_2020/s129_2020.pkl", "2022–2024": "/home/user/mc_oos/s129_2022.pkl", "2024–2026": "/home/user/mc_data/s129_2024.pkl"}
P = {k: pd.read_pickle(v) for k, v in P.items()}
for nm in ("L25/10/48", "L48/S15"):
    print(f"\n=== лонг {nm} ===")
    allx = []
    for k, X in P.items():
        months = (X.t.max() - X.t.min()) / (30.4 * 86400)
        m, t, n = ct(X[nm], X.t); dp, tp, _ = ct(X[nm] - X["pl_" + nm], X.t)
        w = X["why_" + nm]
        print(f"  {k}: n={n} ({n / months:.1f}/мес) {m:+.2%} (t {t:+.1f}) в плюсе {(X[nm] > 0).mean():.0%} тейков {(w == 'тейк').mean():.0%} "
              f"стопов {(w == 'стоп').mean():.0%} | плацебо {X['pl_' + nm].mean():+.2%}, разница {dp:+.2%} (t {tp:+.1f})")
        allx.append(X)
    a = pd.concat(allx); m, t, n = ct(a[nm], a.t); dp, tp, _ = ct(a[nm] - a["pl_" + nm], a.t)
    print(f"  6 лет: n={n} {m:+.2%} (t {t:+.1f}) | сверх плацебо {dp:+.2%} (t {tp:+.1f})")
