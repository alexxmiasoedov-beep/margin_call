"""s81 — события s73 (вход в пятёрку оборота одной корейской биржи без 🔝 за 7 сут) во время ажиотажа рынка: пампов всех
фьючерсов за 24 ч до события ≥ 16 (s15/kr_pumps.pkl, как в s6). Шорт 10/25/48 (основной) и 7 сут; плацебо — из s73.
Запуск из папки с данными (после s73/exch_test.py)."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402


def main():
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    pt = np.sort(np.concatenate([K[s]["t"][v].astype(np.int64) + 900 for s, v in PU.items() if len(v)]))
    X = pd.read_pickle("s73/trades.pkl")
    X["np"] = np.searchsorted(pt, X.t.values, "right") - np.searchsorted(pt, X.t.values - DAY, "right")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий s73: {len(X)}; пампов рынка за 24 ч — медиана {X.np.median():.0f}; в ажиотаж (≥ 16): {(X.np >= 16).mean():.0%}")
    for lab, x0 in (("ажиотаж ≥ 16 (основная)", X[X.np >= 16]), ("10–15 пампов", X[(X.np >= 10) & (X.np < 16)]),
                    ("0–9 пампов", X[X.np < 10])):
        for col in ("S_10_25", "S_7d"):
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:24s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
