"""s83 — объединение событий s73 (пятёрка одной корейской биржи без 🔝 за 7 сут) и s67 (пятёрка пар к лире без прошлых
🔝, 🛒, 🇰🇷 за 24 ч и без 🔝 за 7 сут); одно событие на монету за 7 сут; шорт 10/25/48 (основной) и 7 сут; плацебо —
из исходных наборов (гипотеза — ВЫВОДЫ.md, записана до расчёта). Запуск из папки с данными."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import CUT, DAY, ct  # noqa: E402


def main():
    A = pd.read_pickle("s73/trades.pkl").assign(src="Корея, одна биржа")
    B = pd.read_pickle("s67/trades.pkl").assign(src="лира")
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    kt = {s: g.t.values for s, g in S65.groupby("s")}
    other = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        other.setdefault(s, []).append(t)
    other = {s: np.array(v) for s, v in other.items()}
    keep = []
    for r in B.itertuples():
        o = other.get(r.s, np.zeros(0)); k = kt.get(r.s, np.zeros(0))
        keep.append(not ((o < r.t) & (o >= r.t - DAY)).any() and not ((k <= r.t) & (k >= r.t - 7 * DAY)).any())
    B = B[np.array(keep)]
    cols = ["s", "t", "src", "S_10_25", "pl_S_10_25", "S_7d", "pl_S_7d"]
    U = pd.concat([A[cols], B[cols]]).sort_values("t")
    rows, last = [], {}
    for r in U.itertuples(index=False):
        if r.t - last.get(r.s, -1e18) < 7 * DAY:
            continue
        last[r.s] = r.t; rows.append(r._asdict())
    X = pd.DataFrame(rows)
    X.to_pickle("s83/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий: {len(X)} ({len(X) / months:.1f} в месяц); из них {X.src.value_counts().to_dict()}")
    for lab, x0 in (("объединение (основная)", X), ("только Корея", X[X.src != "лира"]), ("только лира", X[X.src == "лира"])):
        for col in ("S_10_25", "S_7d"):
            x = x0[x0[col].notna()]
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:24s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
