"""s53 — премия фьючерса к индексу спота в пампе (гипотеза — ВЫВОДЫ.md, записана до расчёта). Пампы — s15/kr_pumps.pkl;
премия на закрытии свечи пампа — s12/prem.pkl (время — открытие свечи). Трети — по пампам первой половины. Шорт 10/25/48
с закрытия свечи пампа, одна сделка на монету за 48 ч; плацебо — та же монета за 45/90/135 сут. Пересечение с 🛒 — доля
спота Binance из s49/trades.pkl. Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

EX = dict(tp=0.10, sl=0.25, hold_h=48)


def main():
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    PR = pickle.load(open("s12/prem.pkl", "rb"))
    S49 = pd.read_pickle("s49/trades.pkl")
    share = {(r.s, int(r.t)): (r.share, r.spot) for r in S49.itertuples()}
    rows = []
    for s, pj in PU.items():
        if s not in K or s not in PR or not len(pj):
            continue
        pt, pv = PR[s]
        last = -1e18
        for j in pj:
            t0 = int(K[s]["t"][j]); Tp = t0 + 900
            if Tp - last < 48 * 3600:
                continue
            k = int(np.searchsorted(pt, t0))
            if k >= len(pt) or pt[k] != t0:
                continue
            x = trade(s, j, **EX)
            if x is None:
                continue
            last = Tp
            p = [y["net"] for dd in (45, 90, 135) if j - dd * 96 >= 96 and (y := trade(s, j - dd * 96, **EX))]
            sh, spot = share.get((s, Tp), (np.nan, None))
            rows.append(dict(s=s, t=Tp, prem=float(pv[k]), share=sh, spot=spot, net=x["net"], pl=np.mean(p) if p else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle("s53/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    q1, q2 = X[X.t < CUT].prem.quantile([1 / 3, 2 / 3])
    print(f"Пампов с премией и сделкой: {len(X)} за {months:.1f} мес.; трети премии по первой половине: {q1:+.3%} и {q2:+.3%};"
          f" медиана {X.prem.median():+.3%}")

    def line(lab, x):
        if len(x) < 8:
            return f"  {lab:48s} мало ({len(x)})"
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        a, b = x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()
        return (f"  {lab:48s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} |"
                f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x.pl.mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    low = X[X.prem < q1]
    print(line("ОСНОВНАЯ: нижняя треть премии (спот ведёт)", low))
    print(line("средняя треть", X[(X.prem >= q1) & (X.prem < q2)]))
    print(line("верхняя треть премии (ведут плечи)", X[X.prem >= q2]))
    print(line("  основная без пампов 🛒 (доля спота < 25,9%)", low[~(low.share >= 0.259)]))
    print(line("  основная у монет без спота Binance", low[low.spot == False]))  # noqa: E712
    print(line("  основная вместе с 🛒 (доля спота ≥ 25,9%)", low[low.share >= 0.259]))


if __name__ == "__main__":
    main()
