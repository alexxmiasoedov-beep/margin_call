"""s65 — монета входит в пятёрку по обороту Кореи за 24 ч (гипотеза — ВЫВОДЫ.md, записана до расчёта). Часовой оборот Кореи —
s15/kr_panel.pkl (колонка kr, время — конец часа). Лидеры — 10 монет с наибольшим медианным суточным оборотом на первой
половине (исключаются). Событие — на закрытии часа монета (не лидер) в пятёрке по обороту за 24 ч, за прошлые 7 сут в
пятёрке не была; фьючерс Binance торгуется ≥ суток. Шорт 7 сут со стопом 50% (основной) и 10/25/48; одна сделка на монету
за 7 сут; плацебо — та же монета за 45/90/135 сут; пересечение с корейскими листингами (s15/kr_journal.pkl) в прошлые 7 сут.
Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

EXITS = {"S_7d": dict(tp=None, sl=0.50, hold_h=168), "S_10_25": dict(tp=0.10, sl=0.25, hold_h=48)}


def main():
    KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    V = pd.DataFrame({s: d.set_index("T").kr for s, d in KP.items() if s in K}).sort_index()
    V = V.fillna(0.0)
    V24 = V.rolling(24, min_periods=24).sum()
    h1 = V24[V24.index < CUT]
    majors = list(h1.median().sort_values(ascending=False).index[:10])
    print("лидеры (исключены):", majors)
    R = V24.drop(columns=majors).rank(axis=1, ascending=False, method="first")
    top = R <= 5
    LJ = pd.read_pickle("s15/kr_journal.pkl")
    lst = {s: g.t.values for s, g in LJ.groupby("sym")}
    rows, last = [], {}
    in7 = top.rolling(168, min_periods=1).max().shift(1).fillna(0).astype(bool)   # была ли в пятёрке за прошлые 7 сут
    for T, row in top.iterrows():
        for s in row.index[row.values]:
            if in7.at[T, s] or T - last.get(s, -1e18) < 7 * DAY:
                continue
            lo, hi = live(s)
            if T < lo + DAY or T > hi:
                continue
            i = idx_at(s, T)
            if i is None:
                continue
            last[s] = T
            d = dict(s=s, t=T, krlist=bool(((lst.get(s, np.zeros(0)) <= T) & (lst.get(s, np.zeros(0)) >= T - 7 * DAY)).any()))
            for nm, kw in EXITS.items():
                x = trade(s, i, **kw)
                d[nm] = x["net"] if x else np.nan
                p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **kw))]
                d["pl_" + nm] = np.mean(p) if p else np.nan
            rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s65/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий: {len(X)} ({len(X) / months:.1f} в месяц); после корейского листинга (7 сут): {X.krlist.sum()}")
    for lab, x0 in (("все", X), ("без корейского листинга за 7 сут", X[~X.krlist])):
        for col in EXITS:
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            a, b = x[x.t < CUT][col].mean(), x[x.t >= CUT][col].mean()
            print(f"  {lab:34s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x['pl_' + col].mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
