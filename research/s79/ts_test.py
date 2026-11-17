"""s79 — крупная средняя сделка на фьючерсе (TS из s23/feat_W24.pkl): каждый день в 00:00 UTC шорт пяти монет вселенной
s23 (нормальный часовой оборот ≥ 50 тыс. $) с наибольшим TS; вход на закрытии свечи 00:00–00:15; выход 24 ч, стоп 20%
(основной), 10/25/48 и 72 ч со стопом 25%; плацебо — та же монета за 45/90/135 сут (гипотеза — ВЫВОДЫ.md, записана
до расчёта). Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s23"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

N = 5
EX = {"X_24h": dict(tp=None, sl=0.20, hold_h=24), "S_10_25": dict(tp=0.10, sl=0.25, hold_h=48),
      "X_72h": dict(tp=None, sl=0.25, hold_h=72)}


def entry(s, T):
    t = K[s]["t"]; i = int(np.searchsorted(t, T))
    return i if i < len(t) and t[i] == T and K[s]["qv"][i] > 0 else None


def main():
    F = pickle.load(open("s23/feat_W24.pkl", "rb"))
    TS, Vb, C = F["TS"], F["Vb"], F["C"]
    days = [T for T in TS.index if T % DAY == 0 and T >= TS.index[0] + 40 * DAY]
    rows = []
    for T in days:
        ts = TS.loc[T]; vb = Vb.loc[T]
        ok = ts.index[(vb >= 50e3) & ts.notna() & C.loc[T].notna()]
        cand = []
        for s in ok:
            if s not in K:
                continue
            lo, hi = live(s)
            if T < lo + 30 * DAY or T + 3 * DAY > hi or entry(s, T) is None:
                continue
            cand.append(s)
        if len(cand) < 30:
            continue
        top = ts[cand].sort_values(ascending=False).index[:N]
        allr = {}
        for s in cand:
            x = trade(s, entry(s, T), tp=None, sl=None, hold_h=24, side=-1)
            if x:
                allr[s] = x["price"]
        avg = np.mean(list(allr.values()))
        for s in top:
            i = entry(s, T); c = K[s]["c"]
            d = dict(s=s, t=T, ts=float(ts[s]), r24=float(c[i] / c[i - 96] - 1), rel=allr.get(s, np.nan) - avg)
            for nm, kw in EX.items():
                x = trade(s, i, side=-1, **kw)
                d[nm] = x["net"] if x else np.nan
                p = [y["net"] for dd in (45, 90, 135) if (j := entry(s, T - dd * DAY)) is not None
                     and T - dd * DAY >= live(s)[0] and (y := trade(s, j, side=-1, **kw))]
                d["pl_" + nm] = np.mean(p) if p else np.nan
            rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s79/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Дней среза {X.t.nunique()}, сделок {len(X)} ({len(X) / months:.1f} в месяц); медиана TS {X.ts.median():+.2f};"
          f" рост за 24 ч до входа у {(X.r24 > 0).mean():.0%}; сверх среза за сутки {X.rel.mean():+.2%} (t {ct(X.rel, X.t)[1]:+.1f})")
    for lab, x0 in (("все (основная)", X), ("после роста за 24 ч", X[X.r24 > 0]), ("после падения", X[X.r24 <= 0])):
        for col in EX:
            x = x0[x0[col].notna()]
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:20s} {col:7s} n={n:4d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
