"""s83 — устойчивость объединения: точное t, кварталы, без трёх самых насыщенных дней, вход на час позже, одновременные
позиции. Запуск из папки с данными (после union_test.py)."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s66"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from oi_test import CUT, DAY, ct  # noqa: E402
from attn_test import idx_at, trade  # noqa: E402

KW = dict(tp=0.10, sl=0.25, hold_h=48)


def main():
    X = pd.read_pickle("s83/trades.pkl")
    x = X[X.S_10_25.notna()]
    m, t, n = ct(x.S_10_25, x.t)
    print(f"Основная: n={n}, {m:+.3%}, t = {t:.3f}")
    q = pd.to_datetime(x.t, unit="s").dt.to_period("Q")
    print("По кварталам:", " | ".join(f"{k}: {v.mean():+.2%} ({len(v)})" for k, v in x.groupby(q).S_10_25))
    d = (x.t // DAY)
    top = d.value_counts().index[:3]
    y = x[~d.isin(top)]
    m2, t2, n2 = ct(y.S_10_25, y.t)
    print(f"Без трёх самых насыщенных дней ({', '.join(str(pd.Timestamp(v * DAY, unit='s').date()) for v in top)}): n={n2}, {m2:+.2%}, t {t2:.2f}")
    late = []
    for r in x.itertuples():
        i = idx_at(r.s, r.t + 3600)
        z = trade(r.s, i, **KW) if i is not None else None
        late.append(z["net"] if z else np.nan)
    x = x.assign(late=late)
    z = x[x.late.notna()]
    m3, t3, n3 = ct(z.late, z.t)
    h1, h2 = z[z.t < CUT], z[z.t >= CUT]
    print(f"Вход на час позже: n={n3}, {m3:+.2%}, t {t3:.2f}; половины {h1.late.mean():+.2%} / {h2.late.mean():+.2%}")
    ts = np.sort(x.t.values); ends = ts + 48 * 3600
    conc = max(int(((ts <= s_) & (ends > s_)).sum()) for s_ in ts)
    print(f"Одновременно открытых сделок (по 48 ч) — максимум {conc}")
    print(f"Медиана, винрейт: {x.S_10_25.median():+.2%}, {(x.S_10_25 > 0).mean():.0%}; худшая {x.S_10_25.min():+.1%}")


if __name__ == "__main__":
    main()
