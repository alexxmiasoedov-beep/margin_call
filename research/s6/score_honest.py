"""Честная проверка «счёта условий» для корейского шорта: признаки и пороги выбираются ТОЛЬКО по 1-му году
(разница доходности верхней и нижней трети, лучшие K признаков), счёт = число выполненных условий; проверка на 2-м году."""
import sys
import numpy as np, pandas as pd
D = pd.read_pickle("s6/feat.pkl"); col = sys.argv[1] if len(sys.argv) > 1 else "S_7_20"
OUTC = [c for c in D.columns if c.startswith(("S_", "L_"))]
FE = [c for c in D.columns if c not in OUTC + ["s", "t", "i", "y", "mfe_s24", "mae_s24", "mfe_s48", "mae_s48", "ret48", "ret24", "ret4", "full"]]
Kr = D[D.kshare >= 0.2]; A = Kr[Kr.y == 1]; Bt = Kr[Kr.y == 2]
cand = []
for f in FE:
    x = A[f]
    if x.notna().mean() < 0.7 or x.nunique() < 4 or f in ("kshare",): continue
    lo, hi = x.quantile(1 / 3), x.quantile(2 / 3)
    top = A[x >= hi][col].mean(); bot = A[x <= lo][col].mean()
    if top >= bot: cand.append((top - bot, f, ">=", hi))
    else: cand.append((bot - top, f, "<=", lo))
cand.sort(reverse=True)
tp, sl = (int(v) for v in col.split("_")[1:])
print(f"{col} (безубыточный {sl / (tp + sl):.1%}); признаки, выбранные по 1-му году:")
for d, f, op, th in cand[:8]: print(f"   {f} {op} {th:.4g}  (разница третей на 1-м году {d * 100:+.2f} п. п.)")
for Kn in (3, 5, 7):
    sel = cand[:Kn]
    sc = lambda g: sum(((g[f] >= th) if op == ">=" else (g[f] <= th)).astype(int) for _, f, op, th in sel)
    sA, sB = sc(A), sc(Bt)
    print(f"\n K = {Kn} признаков: счёт → 1-й год (подбор) | 2-й год (проверка)")
    for s in range(Kn + 1):
        a = A[sA == s][col]; b = Bt[sB == s][col]
        if len(a) + len(b) == 0: continue
        print(f"   счёт {s}: 1-й {len(a):4d} WR {(a > 0).mean():.1%} {a.mean() * 100:+.2f}% | 2-й {len(b):4d} WR {(b > 0).mean():.1%} {b.mean() * 100:+.2f}%")
    for s in range(1, Kn + 1):
        b = Bt[sB >= s][col]
        if len(b) >= 30: print(f"   2-й год, счёт ≥ {s}: {len(b)} сделок, WR {(b > 0).mean():.1%}, {b.mean() * 100:+.2f}%")
