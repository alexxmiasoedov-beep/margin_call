"""s102 — разбор совпадений 🇹🇷 и 🇰🇷 (входы ≤ 1 ч, та же монета): сила пампа (рост за 4 ч) против участия Кореи; исходы пар;
что было бы с 🇹🇷 на совпадениях при выходах 🇰🇷 (только наблюдение, найдено после расчёта).
Запуск из папки с данными после tr_kr_overlap.py: python3 <repo>/research/s102/tr_kr_detail.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, ct, idx_at  # noqa: E402

X = pd.read_pickle("s102/trades.pkl")
TR, KR = X[X.j == "🇹🇷"].copy(), X[X.j == "🇰🇷"].copy()
kr = {s: g.t.values for s, g in KR.groupby("s")}
TR["ov"] = [bool(len(kr.get(s, [])) and (np.abs(kr[s] - t) <= 3600).any()) for s, t in zip(TR.s, TR.t)]


def line(x):
    m, t, n = ct(x.net, x.t)
    return f"n={n:4d} {m:+6.2%} (t {t:+4.1f}) стопов {x.stop.mean():4.0%}"


print("🇹🇷 по росту за 4 ч и совпадению с 🇰🇷 (≤ 1 ч):")
for lab, m in (("рост 10–15%", TR.r4 < 0.15), ("рост 15–25%", (TR.r4 >= 0.15) & (TR.r4 < 0.25)), ("рост ≥ 25%", TR.r4 >= 0.25)):
    print(f"  {lab:12s} совпали: {line(TR[m & TR.ov])} | без 🇰🇷: {line(TR[m & ~TR.ov])}")
print(f"  медиана роста за 4 ч: совпали {TR[TR.ov].r4.median():.0%}, без 🇰🇷 {TR[~TR.ov].r4.median():.0%}")

P = []
for _, r in TR[TR.ov].iterrows():
    g = KR[(KR.s == r.s) & ((KR.t - r.t).abs() <= 3600)].iloc[0]
    P.append((r.why, g.why, r.net, g.net))
P = pd.DataFrame(P, columns=["wT", "wK", "nT", "nK"])
print("\nисходы пар (🇹🇷 / 🇰🇷):")
print(pd.crosstab(P.wT, P.wK, margins=True).to_string())
pT, pK = (P.wT == "стоп").mean(), (P.wK == "стоп").mean()
print(f"обе по стопу {((P.wT == 'стоп') & (P.wK == 'стоп')).mean():.0%} пар; если бы стопы были независимы — {pT * pK:.0%}."
      f" 🇹🇷 по стопу, 🇰🇷 — нет: {((P.wT == 'стоп') & (P.wK != 'стоп')).mean():.0%}")

# 🇹🇷 на совпадениях с выходами 🇰🇷 (тейк 10 / стоп 25 / 48 ч) и с отказом от входа — только наблюдение
alt = []
for s, t in zip(TR[TR.ov].s, TR[TR.ov].t):
    i = idx_at(s, t); r = trade(s, i, 0.10, 0.25, 48) if i is not None else None
    alt.append(r["net"] if r else np.nan)
a = pd.Series(alt, index=TR[TR.ov].index)
m, t, n = ct(a, TR[TR.ov].t)
print(f"\n🇹🇷 на совпадениях с выходами 🇰🇷 (10/25/48): {m:+.2%} (t {t:+.1f}, {n}) против своих 10/15/24: {TR[TR.ov].net.mean():+.2%}")
tot, skip = TR.net.sum(), TR[~TR.ov].net.sum()
print(f"итог 🇹🇷 за два года (маржа 1 на сделку): все {tot:+.2f}, без совпадений {skip:+.2f};"
      f" на сделку {TR.net.mean():+.2%} → {TR[~TR.ov].net.mean():+.2%}")
