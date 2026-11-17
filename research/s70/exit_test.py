"""s70 — выход из корейской пятёрки (гипотеза — ВЫВОДЫ.md, записана до расчёта). Часовой оборот Кореи — s15/kr_panel.pkl;
сумма за 24 ч; лидеры — те же 10, что у 🔝 (медиана первой половины). Событие: на закрытии часа T монета не в пятёрке,
час назад была в ней и пробыла там ≥ 24 ч подряд; фьючерс старше суток; одно событие на монету за 7 сут. Шорт 7 сут со
стопом 50% (основной) и 10/25/48; плацебо — та же монета за 45/90/135 сут; пересечение — вход 🔝 (s65/trades.pkl)
за прошлые 48 ч. Запуск из папки с данными."""
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
    V = pd.DataFrame({s: d.set_index("T").kr for s, d in KP.items() if s in K}).sort_index().fillna(0.0)
    V24 = V.rolling(24, min_periods=24).sum()
    majors = list(V24[V24.index < CUT].median().sort_values(ascending=False).index[:10])
    R = V24.drop(columns=majors).rank(axis=1, ascending=False, method="first")
    top = (R <= 5) & V24.drop(columns=majors).notna()
    a = top.values.astype(np.int32); r = np.zeros_like(a)                    # сколько часов подряд в пятёрке
    for k in range(len(a)):
        r[k] = (r[k - 1] + 1) * a[k] if k else a[k]
    run = pd.DataFrame(r, index=top.index, columns=top.columns)
    ev = (~top) & (run.shift(1) >= 24)
    S65 = pd.read_pickle("s65/trades.pkl")
    kt = {s: g.t.values for s, g in S65.groupby("s")}
    rows, last = [], {}
    for T, row in ev.iterrows():
        T = int(T)
        for s in row.index[row.values]:
            if T - last.get(s, -1e18) < 7 * DAY:
                continue
            lo, hi = live(s)
            if T < lo + DAY or T > hi:
                continue
            i = idx_at(s, T)
            if i is None:
                continue
            last[s] = T
            o = kt.get(s, np.zeros(0))
            d = dict(s=s, t=T, stay=int(run.at[T - 3600, s]), rank=float(R.at[T, s]),
                     kt=bool(((o < T) & (o >= T - 2 * DAY)).any()))
            for nm, kw in EXITS.items():
                x = trade(s, i, **kw)
                d[nm] = x["net"] if x else np.nan
                p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **kw))]
                d["pl_" + nm] = np.mean(p) if p else np.nan
            rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s70/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Лидеры: {majors}\nСобытий: {len(X)} ({len(X) / months:.1f} в месяц); с открытой 🔝 (вход за 48 ч): {X.kt.mean():.0%};"
          f" медиана пребывания {X.stay.median():.0f} ч")
    for lab, x0 in (("все (основная)", X), ("без открытой 🔝", X[~X.kt])):
        for col in EXITS:
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:16s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
