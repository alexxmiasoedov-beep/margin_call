"""s60 — медленный подъём со спотом (гипотеза — ВЫВОДЫ.md, записана до расчёта). На закрытии часа фьючерс за 24 ч ≥ +20%,
без резкого пампа (s15/kr_pumps.pkl) за эти 24 ч, у монеты есть спот Binance; не чаще раза в 48 ч. Доля спота за 24 ч =
спот / (спот + фьючерс). Трети — по первой половине. Шорт 10/25/48 с закрытия часа; плацебо — та же монета за
45/90/135 сут; пересечение с 🛒 (s49) в ±24 ч. Запуск из папки с данными."""
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
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    cart = {s: g.t.values for s, g in S49.groupby("s")}
    rows = []
    for s, sp in SP.items():
        if s not in K:
            continue
        a = K[s]; c = a["c"].astype(float); t = a["t"].astype(np.int64); qv = a["qv"].astype(float)
        cq = np.r_[0.0, np.cumsum(qv)]
        spT = sp[:, 0].astype(np.int64) + 3600; spv = sp[:, 1].astype(float); cs = np.r_[0.0, np.cumsum(spv)]
        pu = np.asarray(PU.get(s, []), dtype=np.int64)
        j = np.flatnonzero(((t + 900) % 3600 == 0) & (np.arange(len(t)) >= 96))
        last = -1e18
        for jj in j:
            if qv[jj] <= 0 or c[jj - 96] <= 0 or c[jj] / c[jj - 96] - 1 < 0.20:
                continue
            Te = int(t[jj]) + 900
            if Te - last < 48 * 3600 or ((pu > jj - 96) & (pu <= jj)).any():
                continue
            k1 = int(np.searchsorted(spT, Te, side="right")); k0 = int(np.searchsorted(spT, Te - 86400, side="right"))
            s24 = cs[k1] - cs[k0]; f24 = cq[jj + 1] - cq[jj - 95]
            if f24 <= 0:
                continue
            x = trade(s, jj, **EX)
            if x is None:
                continue
            last = Te
            p = [y["net"] for dd in (45, 90, 135) if jj - dd * 96 >= 96 and (y := trade(s, jj - dd * 96, **EX))]
            tt = cart.get(s, np.zeros(0))
            rows.append(dict(s=s, t=Te, share=s24 / max(s24 + f24, 1.0), r24=c[jj] / c[jj - 96] - 1, net=x["net"],
                             pl=np.mean(p) if p else np.nan, cart=bool((np.abs(tt - Te) <= 86400).any())))
    X = pd.DataFrame(rows)
    X.to_pickle("s60/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    q1, q2 = X[X.t < CUT].share.quantile([1 / 3, 2 / 3])
    print(f"Медленных подъёмов со сделкой: {len(X)} ({len(X) / months:.0f} в месяц); трети доли спота за 24 ч: {q1:.1%} и {q2:.1%}")

    def line(lab, x):
        if len(x) < 8:
            return f"  {lab:38s} мало ({len(x)})"
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        a, b = x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()
        return (f"  {lab:38s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} |"
                f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x.pl.mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    print(line("нижняя треть доли спота", X[X.share < q1]))
    print(line("средняя треть", X[(X.share >= q1) & (X.share < q2)]))
    top = X[X.share >= q2]
    print(line("ОСНОВНАЯ: верхняя треть", top))
    print(line("  без входа 🛒 в ±24 ч", top[~top.cart]))


if __name__ == "__main__":
    main()
