"""s122 — сводка по трём периодам (после tsmom.py в ~/mc_2020, ~/mc_oos, ~/mc_data)."""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import ct  # noqa: E402

P = {"2020–2022": "/home/user/mc_2020/s122_2020.pkl", "2022–2024": "/home/user/mc_oos/s122_2022.pkl", "2024–2026": "/home/user/mc_data/s122_2024.pkl"}
P = {k: pd.read_pickle(v) for k, v in P.items()}
allx = []
for k, X in P.items():
    months = (X.t.max() - X.t.min()) / (30.4 * 86400)
    m, t, n = ct(X.net, X.t)
    lo, sh = X[X.side == 1], X[X.side == -1]
    print(f"{k}: n={n} ({n / months:.0f}/мес) тренд {m:+.2%} (t {t:+.1f}) | лонги {lo.net.mean():+.2%} ({len(lo)}, фандинг {lo.fund.mean():+.2%}) "
          f"| шорты {sh.net.mean():+.2%} ({len(sh)}, фандинг {sh.fund.mean():+.2%}) | всегда лонг {X.L.mean():+.2%} | всегда шорт {X.S.mean():+.2%}")
    allx.append(X)
a = pd.concat(allx); m, t, n = ct(a.net, a.t)
print(f"6 лет: n={n} тренд {m:+.2%} (t {t:+.1f}) | лонги {a[a.side == 1].net.mean():+.2%} | шорты {a[a.side == -1].net.mean():+.2%} | "
      f"всегда лонг {a.L.mean():+.2%} | всегда шорт {a.S.mean():+.2%}")
