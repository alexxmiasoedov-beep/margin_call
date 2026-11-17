"""s108 — подбор лонг-правила ТОЛЬКО на первой половине (вход и выход до 01.12.2025), небольшая сетка, всё перечислено:
A — ранг фандинга за 3 сут внутри дня в [lo, hi): (0,1–0,4), (0,1–0,3), (0,05–0,4);
B — ранг волатильности за 7 сут внутри дня < v: 0,5 или 1 (без ограничения);
C — средний фандинг рынка не в верхней трети своих 90 прошлых дней (да/нет).
Отбор дня — до N = 3 монет с наименьшей волатильностью; одна сделка на монету за 7 сут. Доход — лонг на 7 сут без стопа
(L7 из панели: цена − комиссия + полученный фандинг). Печатает все 12 вариантов. Запуск из папки с данными после
long_map2.py: python3 <repo>/research/s108/long_grid.py"""
import itertools
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import CUT, DAY, ct  # noqa: E402

X = pd.read_pickle("s108/panel.pkl")
X["fr"] = X.groupby("t").fund3.rank(pct=True, method="first")
X["vr"] = X.groupby("t").vol7.rank(pct=True, method="first")
M = X.groupby("t").fund3.mean()
hot = (M > M.rolling(90, min_periods=60).quantile(2 / 3).shift(1))      # перегретый рынок по прошлым 90 дням
X["hot"] = X.t.map(hot).fillna(False).astype(bool)


def pick(x, lo, hi, v, cflt, N=3):
    y = x[(x.fr >= lo) & (x.fr < hi) & (x.vr < v)]
    if cflt:
        y = y[~y.hot]
    y = y.sort_values(["t", "vol7"]).groupby("t").head(N * 3)
    out, last = [], {}
    for t, g in y.groupby("t"):
        k = 0
        for s, r in zip(g.s, g.L7):
            if k >= N or t - last.get(s, -1e18) < 7 * DAY:
                continue
            last[s] = t; k += 1
            out.append((s, t, r))
    return pd.DataFrame(out, columns=["s", "t", "L7"])


if __name__ == "__main__":
    F = X[X.t + 7 * DAY < CUT]
    months = (F.t.max() - F.t.min()) / (30.4 * DAY)
    print(f"первая половина, дней {F.t.nunique()}; «перегретых» дней {F.groupby('t').hot.first().mean():.0%}")
    for (lo, hi), v, c in itertools.product(((0.1, 0.4), (0.1, 0.3), (0.05, 0.4)), (0.5, 1.0), (True, False)):
        T = pick(F, lo, hi, v, c)
        m, t, n = ct(T.L7, T.t)
        print(f"  фандинг {lo:.2f}–{hi:.2f}, волатильность < {v:.1f}, фильтр рынка {'да' if c else 'нет'}: "
              f"n={n:4d} ({n / months:5.1f}/мес) {m:+.2%} (t {t:+.1f}) в плюсе {(T.L7 > 0).mean():.0%}")
