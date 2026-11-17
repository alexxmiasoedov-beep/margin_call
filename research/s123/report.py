"""s123 — сводка по двум периодам (после drop9.py в ~/mc_oos и ~/mc_data)."""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import ct  # noqa: E402

P = {"2022–2024": "/home/user/mc_oos/s123_2022.pkl", "2024–2026": "/home/user/mc_data/s123_2024.pkl"}
P = {k: pd.read_pickle(v) for k, v in P.items()}
for col in ("L_10_25", "L_24h"):
    print(f"\n=== лонг {col} ===")
    for lab, f in (("01:00 UTC (правило)", lambda x: x.open9), ("другие часы (контроль)", lambda x: ~x.open9)):
        cells, allx = [], []
        for k, X in P.items():
            x = X[f(X) & X[col].notna()]
            months = (X.t.max() - X.t.min()) / (30.4 * 86400)
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            cells.append(f"{k}: n={n} ({n / months:.1f}/мес) {m:+.2%} (t {t:+.1f}), сверх плацебо {dp:+.2%} (t {tp:+.1f})")
            allx.append(x)
        a = pd.concat(allx); m, t, n = ct(a[col], a.t); dp, tp, _ = ct(a[col] - a["pl_" + col], a.t)
        print(f"  {lab:24s} | " + " | ".join(cells) + f" | вместе: n={n} {m:+.2%} (t {t:+.1f}), сверх плацебо {dp:+.2%} (t {tp:+.1f})")
