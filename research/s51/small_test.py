"""s51 — малые пампы (+10% за ≤ 2 ч из покоя) с долей спота Binance (гипотеза — ВЫВОДЫ.md, записана до расчёта). Детектор —
как s15/kr_panel.pumps, порог 10%. Доля спота за последний полный час до закрытия свечи пампа; граница верхней трети —
по пампам первой половины. Шорт 10/25/48 с закрытия свечи пампа, одна сделка на монету за 48 ч; плацебо — та же монета
за 45/90/135 сут. Отдельно — дошёл ли памп до +15% за следующие 2 ч (s15/kr_pumps.pkl) и пересечение с 🛒 (s49).
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


def pumps(a, thr):
    c, h = a["c"].astype(float), a["h"].astype(float); n = len(c)
    calm = np.zeros(n, bool); calm[8:] = np.abs(c[8:] / c[:-8] - 1) <= 0.05
    hit = np.zeros(n, bool); hs = pd.Series(h)
    for L in range(1, 9):
        mx = hs.rolling(L, min_periods=L).max().values
        base = np.r_[np.full(L, np.nan), c[:-L]]; cb = np.r_[np.zeros(L, bool), calm[:-L]]
        hit |= cb & (mx >= base * (1 + thr)) & (np.arange(n) - L >= 8)
    nz = np.flatnonzero(a["qv"] > 0)
    if not len(nz):
        return np.array([], dtype=np.int64)
    hit &= (np.arange(n) >= nz[0] + 96) & (np.arange(n) <= nz[-1]) & (a["qv"] > 0)
    out, last = [], -10 ** 9
    for j in np.flatnonzero(hit):
        if j - last >= 96:
            out.append(int(j)); last = j
    return np.array(out, dtype=np.int64)


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
            if Tp - last < 48 * 3600:
                continue
            H = (Tp // 3600) * 3600
            v, pv = float(spv.get(H, np.nan)), float(perp.get(H, np.nan))
            if not (v == v and pv == pv):
                continue
            x = trade(s, j, **EX)
            if x is None:
                continue
            last = Tp
            p = [y["net"] for dd in (45, 90, 135) if j - dd * 96 >= 96 and (y := trade(s, j - dd * 96, **EX))]
            tt = sp_in.get(s, np.zeros(0))
            rows.append(dict(s=s, t=Tp, share=v / max(v + pv, 1.0), net=x["net"], pl=np.mean(p) if p else np.nan,
                             to15=bool(((big >= j) & (big <= j + 8)).any()), cart=bool((np.abs(tt - Tp) <= 12 * 3600).any())))
    X = pd.DataFrame(rows)
    X.to_pickle("s51/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    q2 = X[X.t < CUT].share.quantile(2 / 3)
    print(f"Малых пампов со спотом и сделкой: {len(X)} за {months:.1f} мес. ({len(X) / months:.0f} в месяц); дошли до +15%"
          f" за 2 ч: {X.to15.mean():.0%}; граница верхней трети по первой половине: {q2:.1%}")

    def line(lab, x):
        if len(x) < 8:
            return f"  {lab:46s} мало ({len(x)})"
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        a, b = x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()
        return (f"  {lab:46s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} |"
                f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x.pl.mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    top = X[X.share >= q2]
    print(line("все малые пампы со спотом", X))
    print(line("нижние две трети доли спота", X[X.share < q2]))
    print(line("ОСНОВНАЯ: верхняя треть доли спота", top))
    print(line("  из них не дошли до +15% (новые)", top[~top.to15]))
    print(line("  из них дошли до +15%", top[top.to15]))
    print(line("  без входа 🛒 по монете в ±12 ч", top[~top.cart]))


if __name__ == "__main__":
    main()
