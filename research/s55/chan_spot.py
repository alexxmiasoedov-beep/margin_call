"""s55 — сигнал канала 📘 с долей спота Binance (гипотеза — ВЫВОДЫ.md, записана до расчёта). Сигналы — s16/channel_korea
(монета в канале ≥ 4 ч, рост за 4 ч +8…+17%, кулдаун 24 ч); доля спота за последний полный час до закрытия свечи сигнала
(s23/spot1h.pkl, фьючерс — s2/k2y.pkl). Трети — по сигналам первой половины. Выход 📘: тейк 15 / стоп 25 / 24 ч; плацебо —
та же монета за 45/90/135 сут; пересечение с 🛒 (s49). Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s16", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from channel_korea import channel_signals  # noqa: E402

EX = dict(tp=0.15, sl=0.25, hold_h=24)


def main():
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    cart = {s: g.t.values for s, g in S49.groupby("s")}
    E = channel_signals()
    perp_h = {}
    rows = []
    for e in E.itertuples():
        s, j, T = e.s, e.j, int(e.T)
        a = K[s]
        if s not in perp_h:
            Tend = a["t"].astype(np.int64) + 900
            perp_h[s] = pd.Series(a["qv"].astype(float)).groupby(((Tend - 1) // 3600 + 1) * 3600).sum()
        H = (T // 3600) * 3600
        share = np.nan; spot = s in SP
        if spot:
            sp = SP[s]; m = np.flatnonzero(sp[:, 0].astype(np.int64) == H - 3600)
            v = float(sp[m[0], 1]) if len(m) else np.nan; pv = float(perp_h[s].get(H, np.nan))
            if v == v and pv == pv:
                share = v / max(v + pv, 1.0)
        x = trade(s, j, **EX)
        if x is None:
            continue
        p = [y["net"] for dd in (45, 90, 135) if j - dd * 96 >= 96 and (y := trade(s, j - dd * 96, **EX))]
        tt = cart.get(s, np.zeros(0))
        rows.append(dict(s=s, t=T, spot=spot, share=share, net=x["net"], pl=np.mean(p) if p else np.nan,
                         cart=bool((np.abs(tt - T) <= 12 * 3600).any())))
    X = pd.DataFrame(rows)
    X.to_pickle("s55/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    q1, q2 = X[(X.t < CUT) & X.share.notna()].share.quantile([1 / 3, 2 / 3])
    print(f"Сигналов 📘 со сделкой: {len(X)} за {months:.1f} мес.; трети доли спота по первой половине: {q1:.1%} и {q2:.1%}")

    def line(lab, x):
        if len(x) < 8:
            return f"  {lab:40s} мало ({len(x)})"
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        a, b = x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()
        return (f"  {lab:40s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} |"
                f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x.pl.mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    print(line("все сигналы 📘", X))
    print(line("монеты без спота Binance", X[~X.spot]))
    print(line("нижняя треть доли спота", X[X.share < q1]))
    print(line("средняя треть", X[(X.share >= q1) & (X.share < q2)]))
    top = X[X.share >= q2]
    print(line("ОСНОВНАЯ: верхняя треть доли спота", top))
    print(line("  без входа 🛒 по монете в ±12 ч", top[~top.cart]))


if __name__ == "__main__":
    main()
