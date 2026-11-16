"""s49 — доля спота Binance в пампе (гипотеза — ВЫВОДЫ.md, записана до расчёта). Пампы — s15/kr_pumps.pkl; доля спота =
спот / (спот + фьючерс) по обороту за последний полный час до закрытия свечи пампа (спот — s23/spot1h.pkl, фьючерс — 15-мин
свечи s2/k2y.pkl); доля агрессивных покупок спота за тот же час. Граница верхней трети — по пампам первой половины.
Шорт с закрытия свечи пампа, 10/25/48 ч, одна сделка на монету за 48 ч; плацебо — та же монета за 45/90/135 сут.
Запуск из папки с данными."""
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
    KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    rows = []
    for s, pj in PU.items():
        if s not in K or not len(pj):
            continue
        a = K[s]; Tend = a["t"].astype(np.int64) + 900
        H = ((Tend - 1) // 3600 + 1) * 3600
        perp = pd.Series(a["qv"].astype(float)).groupby(H).sum()
        sp = SP.get(s)
        if sp is not None:
            spv = pd.Series(sp[:, 1], index=sp[:, 0].astype(np.int64) + 3600)
            sptb = pd.Series(sp[:, 2], index=sp[:, 0].astype(np.int64) + 3600)
        kp = KP.get(s)
        last = -1e18
        for j in pj:
            Tp = int(a["t"][j]) + 900
            if Tp - last < 48 * 3600:
                continue
            Hh = (Tp // 3600) * 3600
            share = tb = np.nan
            if sp is not None:
                v = float(spv.get(Hh, np.nan)); pv = float(perp.get(Hh, np.nan))
                if v == v and pv == pv:
                    share = v / max(v + pv, 1.0)
                    tb = float(sptb.get(Hh, np.nan)) / v if v > 0 else np.nan
            kr = np.nan
            if kp is not None:
                Tv = kp["T"].values; k = int(np.searchsorted(Tv, Tp, side="right")) - 1
                kr = float(kp["share"].values[k]) if k >= 0 and Tp - Tv[k] < 3600 else np.nan
            x = trade(s, j, **EX)
            if x is None:
                continue
            last = Tp
            p = [y["net"] for dd in (45, 90, 135) if j - dd * 96 >= 96 and (y := trade(s, j - dd * 96, **EX))]
            rows.append(dict(s=s, t=Tp, spot=sp is not None, share=share, tb=tb, kr=kr, net=x["net"],
                             pl=np.mean(p) if p else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle("s49/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    h1 = X[(X.t < CUT) & X.share.notna()]
    q1, q2 = h1.share.quantile([1 / 3, 2 / 3])
    print(f"Пампов со сделкой: {len(X)} за {months:.1f} мес.; со спотом Binance {X.spot.sum()}; границы третей по первой"
          f" половине: {q1:.1%} и {q2:.1%}")

    def line(lab, x):
        if len(x) < 8:
            return f"  {lab:48s} мало ({len(x)})"
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        a, b = x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()
        return (f"  {lab:48s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} |"
                f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x.pl.mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    print(line("все пампы", X))
    print(line("монеты без спота Binance", X[~X.spot]))
    print(line("нижняя треть доли спота", X[X.share < q1]))
    print(line("средняя треть", X[(X.share >= q1) & (X.share < q2)]))
    print(line("ОСНОВНАЯ: верхняя треть доли спота", X[X.share >= q2]))
    print(line("  то же без пампов с долей Кореи ≥ 20%", X[(X.share >= q2) & ~(X.kr >= 0.2)]))
    print(line("вариант: верхняя треть и покупки на споте ≥ 55%", X[(X.share >= q2) & (X.tb >= 0.55)]))


if __name__ == "__main__":
    main()
