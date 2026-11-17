"""s108 — пара «лонг монеты с умеренно отрицательной премией + шорт монеты с фандингом на базовом уровне», подбор ТОЛЬКО
на первой половине (вход и выход до 01.12.2025). Каждый день 00:00 UTC: лонг-нога — ранг фандинга за 3 сут внутри дня
в [0,1; 0,4) и ранг волатильности < v, до 3 монет с наименьшей волатильностью; шорт-нога — ранг фандинга в [0,7; 0,9)
и ранг волатильности ≥ w, до 3 монет с наибольшей волатильностью. Пара — лонг i-й монеты + шорт i-й, равные суммы, 7 сут,
без стопа. Доход пары = L7 лонга + (−цена шорта − 0,001 + фандинг шорту). Одна позиция на монету за 7 сут. Печатает все
варианты сетки (v × w = 3 × 3). Запуск из папки с данными после long_map.py: python3 <repo>/research/s108/pair_grid.py"""
import itertools
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import funding  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

X = pd.read_pickle("s108/panel.pkl")
X["fr"] = X.groupby("t").fund3.rank(pct=True, method="first")
X["vr"] = X.groupby("t").vol7.rank(pct=True, method="first")
_fc = {}


def f7(s, d):
    fr = _fc.setdefault(s, funding(s))
    return float(fr[(fr[:, 0] > d) & (fr[:, 0] <= d + 7 * DAY), 1].sum()) if len(fr) else 0.0


X["S7"] = -(X.L7 + 0.001 + [f7(s, d) for s, d in zip(X.s, X.t)]) - 0.001 + [f7(s, d) for s, d in zip(X.s, X.t)]


def pairs(x, v, w, N=3):
    out, last = [], {}
    for t, g in x.groupby("t"):
        L = g[(g.fr >= 0.1) & (g.fr < 0.4) & (g.vr < v)].sort_values("vol7")
        S = g[(g.fr >= 0.7) & (g.fr < 0.9) & (g.vr >= w)].sort_values("vol7", ascending=False)
        L = [r for r in L.itertuples() if t - last.get(r.s, -1e18) >= 7 * DAY][:N]
        S = [r for r in S.itertuples() if t - last.get(r.s, -1e18) >= 7 * DAY][:N]
        for a, b in zip(L, S):
            last[a.s] = t; last[b.s] = t
            out.append((t, a.s, b.s, a.L7, b.S7))
    P = pd.DataFrame(out, columns=["t", "long", "short", "rl", "rs"])
    P["pair"] = P.rl + P.rs
    return P


if __name__ == "__main__":
    F = X[X.t + 7 * DAY < CUT]
    months = (F.t.max() - F.t.min()) / (30.4 * DAY)
    for v, w in itertools.product((0.5, 0.7, 1.0), (0.0, 0.3, 0.5)):
        P = pairs(F, v, w)
        m, t, n = ct(P.pair, P.t)
        print(f"  лонг: волатильность < {v:.1f}; шорт: волатильность ≥ {w:.1f}: пар {n:4d} ({n / months:5.1f}/мес) "
              f"{m:+.2%} (t {t:+.1f}) в плюсе {(P.pair > 0).mean():.0%} | лонг-нога {P.rl.mean():+.2%}, шорт-нога {P.rs.mean():+.2%}")
