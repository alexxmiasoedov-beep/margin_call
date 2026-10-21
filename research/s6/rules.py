"""Поиск простых правил с высоким винрейтом: базовое множество (корейский сигнал, турецкий, все пампы) + 1–2 условия
вида «признак в верхней/нижней трети» (пороги — по 1-му году). Отбор только по 1-му году, проверка на 2-м."""
import itertools, sys
import numpy as np, pandas as pd
D = pd.read_pickle("s6/feat.pkl")
OUTC = [c for c in D.columns if c.startswith(("S_", "L_"))]
FE = [c for c in D.columns if c not in OUTC + ["s", "t", "i", "y", "mfe_s24", "mae_s24", "mfe_s48", "mae_s48", "ret48", "ret24", "ret4", "full"]]
FE = [c for c in FE if D[c].notna().mean() > 0.5 and D[c].nunique() > 3]
base_name, col = sys.argv[1], sys.argv[2]
BASES = {"korea": D.kshare >= 0.2, "all": D.t > 0, "korea10": D.kshare >= 0.1, "nokt": (D.kshare < 0.2) & (D.fshare < 0.1)}
Bm = BASES[base_name]; Y1 = D.y == 1
tp, sl = (int(x) for x in col.split("_")[1:]); be = sl / (tp + sl)
def stats(m):
    g = D[m & Bm]; g1 = g[g.y == 1]; g2 = g[g.y == 2]
    return len(g1), (g1[col] > 0).mean(), g1[col].mean(), len(g2), (g2[col] > 0).mean(), g2[col].mean()
conds = []
for f in FE:
    x = D.loc[Bm & Y1, f].dropna()
    if len(x) < 60: continue
    lo, hi = x.quantile(1 / 3), x.quantile(2 / 3)
    conds += [(f"{f} ≤ {lo:.4g}", D[f] <= lo), (f"{f} ≥ {hi:.4g}", D[f] >= hi)]
n1, w1, p1, n2, w2, p2 = stats(D.t > 0)
print(f"{base_name} {col} (безубыточный винрейт {be:.1%}): 1-й год {n1} сделок, винрейт {w1:.1%}, {p1*100:+.2f}% | 2-й год {n2}, {w2:.1%}, {p2*100:+.2f}%")
res = []
for (a, ma) in conds:
    res.append((a, "", *stats(ma)))
for (a, ma), (b, mb) in itertools.combinations(conds, 2):
    if a.split(" ")[0] == b.split(" ")[0]: continue
    s = stats(ma & mb)
    if s[0] >= 40: res.append((a, b, *s))
R = pd.DataFrame(res, columns=["условие 1", "условие 2", "n1", "WR1", "pnl1", "n2", "WR2", "pnl2"])
R = R[R.n1 >= 40]
top = R.sort_values("pnl1", ascending=False).head(15)
print("лучшие по 1-му году → как на 2-м:"); print(top.assign(WR1=top.WR1.map("{:.1%}".format), WR2=top.WR2.map("{:.1%}".format), pnl1=(top.pnl1 * 100).round(2), pnl2=(top.pnl2 * 100).round(2)).to_string(index=False))
print(f"\nвсего правил {len(R)}; у 50 лучших по 1-му году 2-й год: средний {R.sort_values('pnl1', ascending=False).head(50).pnl2.mean()*100:+.2f}%, "
      f"в плюсе {(R.sort_values('pnl1', ascending=False).head(50).pnl2 > 0).mean():.0%}; корреляция рангов 1-й/2-й {R.pnl1.rank().corr(R.pnl2.rank()):.2f}")
