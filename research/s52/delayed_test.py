"""s52 — «выдохшийся» малый памп со спотом (гипотеза — ВЫВОДЫ.md, записана до расчёта). Малые пампы s51 (+10% за ≤ 2 ч из
покоя), доля спота за последний полный час до свечи +10% ≥ 26,6%; вход через 8 свечей (2 ч), если за это время не было пампа
+15% (s15/kr_pumps.pkl). Шорт 10/25/48 с закрытия восьмой свечи, одна сделка на монету за 48 ч; плацебо — та же монета
за 45/90/135 сут. Сравнение — тот же вход у пампов с меньшей долей спота. Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s51"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from small_test import pumps  # noqa: E402

EX = dict(tp=0.10, sl=0.25, hold_h=48)
Q2, WAIT = 0.266, 8


def main():
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    SPT = pd.read_pickle("s49/trades.pkl"); SPT = SPT[SPT.share >= 0.259]
    sp_in = {s: g.t.values for s, g in SPT.groupby("s")}
    rows = []
    for s, sp in SP.items():
        if s not in K:
            continue
        a = K[s]
        Tend = a["t"].astype(np.int64) + 900
        perp = pd.Series(a["qv"].astype(float)).groupby(((Tend - 1) // 3600 + 1) * 3600).sum()
        spv = pd.Series(sp[:, 1], index=sp[:, 0].astype(np.int64) + 3600)
        big = PU.get(s, np.array([], dtype=np.int64))
        last = -1e18
        for j in pumps(a, 0.10):
            Tp = int(a["t"][j]) + 900
            H = (Tp // 3600) * 3600
            v, pv = float(spv.get(H, np.nan)), float(perp.get(H, np.nan))
            if not (v == v and pv == pv):
                continue
            if ((big >= j) & (big <= j + WAIT)).any():                 # за 2 ч дошёл до +15% — не входим
                continue
            je = j + WAIT; Te = int(a["t"][je]) + 900 if je < len(a["t"]) else None
            if Te is None or Te - last < 48 * 3600:
                continue
            x = trade(s, je, **EX)
            if x is None:
                continue
            last = Te
            p = [y["net"] for dd in (45, 90, 135) if je - dd * 96 >= 96 and (y := trade(s, je - dd * 96, **EX))]
            tt = sp_in.get(s, np.zeros(0))
            rows.append(dict(s=s, t=Te, share=v / max(v + pv, 1.0), net=x["net"], pl=np.mean(p) if p else np.nan,
                             cart=bool((np.abs(tt - Te) <= 12 * 3600).any())))
    X = pd.DataFrame(rows)
    X.to_pickle("s52/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Входов через 2 ч (малый памп со спотом, до +15% не дошёл): {len(X)} за {months:.1f} мес.")

    def line(lab, x):
        if len(x) < 8:
            return f"  {lab:40s} мало ({len(x)})"
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        h1, h2 = x[x.t < CUT], x[x.t >= CUT]
        (m1, t1, _), (m2, t2, _) = ct(h1.net, h1.t), ct(h2.net, h2.t)
        return (f"  {lab:40s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} |"
                f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x.pl.mean():+6.2%},"
                f" разница {dp:+6.2%} (t {tp:+4.1f})")

    print(line("ОСНОВНАЯ: доля спота ≥ 26,6%", X[X.share >= Q2]))
    print(line("  без входа 🛒 по монете в ±12 ч", X[(X.share >= Q2) & ~X.cart]))
    print(line("сравнение: доля спота < 26,6%", X[X.share < Q2]))


if __name__ == "__main__":
    main()
