"""s126 — 🌊 по разрыву фандинга Binance и Hyperliquid (гипотеза — ВЫВОДЫ.md, записана до расчёта). Сделки — s23/rule_trades.pkl
(ставка ≤ −1%, стоп 15%: net0.15); ставка HL за интервал Binance до T (сумма часовых ставок за ih ч) из s126/hl.pkl.
A — на HL и разрыв (HL − Binance) ≥ 0,5 п. п.; B — на HL, разрыв меньше; C — монеты на HL нет. Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import CUT, ct  # noqa: E402

R = pd.read_pickle("s23/rule_trades.pkl"); R = R[R.rate <= -0.01].copy()
HL = pickle.load(open("s126/hl.pkl", "rb"))
gap, hlr = [], []
for s, T, ih, rate in zip(R.s, R["T"].astype(int), R.ih, R.rate):
    v = HL.get((s, T))
    if not v:
        gap.append(np.nan); hlr.append(np.nan); continue
    h = float(np.sum(v[-int(ih):]))
    hlr.append(h); gap.append(h - rate)
R["hl"] = hlr; R["gap"] = gap
R["g"] = np.where(R.gap.isna(), "C", np.where(R.gap >= 0.005, "A", "B"))
print(f"сделок 🌊: {len(R)}, с данными HL: {(~R.gap.isna()).sum()} (запрошено {len(HL)}); медианный разрыв {R.gap.median():+.2%}")
for g, lab in (("A", "A: на HL, разрыв ≥ 0,5 п. п."), ("B", "B: на HL, разрыв меньше"), ("C", "C: монеты на HL нет")):
    x = R[R.g == g]
    if len(x) < 5:
        print(f"  {lab}: n={len(x)}"); continue
    m, t, n = ct(x["net0.15"], x["T"]); h1, h2 = x[x["T"] < CUT], x[x["T"] >= CUT]
    print(f"  {lab:32s} n={n:4d} {m:+.2%} (t {t:+.1f}) в плюсе {(x['net0.15'] > 0).mean():.0%} | половины {h1['net0.15'].mean():+.2%} "
          f"({len(h1)}) / {h2['net0.15'].mean():+.2%} ({len(h2)}) | медианный разрыв {x.gap.median():+.2%}")
a, c = R[R.g == "A"], R[R.g == "C"]
if len(a) >= 5 and len(c) >= 5:
    d = a["net0.15"].mean() - c["net0.15"].mean(); se = np.sqrt(a["net0.15"].var() / len(a) + c["net0.15"].var() / len(c))
    print(f"  A − C: {d:+.2%} (t ≈ {d / se:+.1f})")
q = pd.qcut(R.gap.dropna(), 4, labels=False)
print("  по четвертям разрыва:", " | ".join(f"{k + 1}: {R.loc[q.index[q == k], 'net0.15'].mean():+.2%} (разрыв ~{R.loc[q.index[q == k], 'gap'].median():+.2%})" for k in range(4)))
