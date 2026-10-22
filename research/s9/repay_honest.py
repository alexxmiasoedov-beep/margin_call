"""Честный отбор правила «шорт после всплеска отдачи»: пороги выбираются только по 1-й половине (до 01.12.2025), проверка — 2-я."""
import itertools
import numpy as np, pandas as pd
S = pd.read_pickle("s9/repay_cand.pkl"); B = pd.read_pickle("s9/repay_base.pkl")
def dedup(g, h=24):
    g = g.sort_values("t"); keep = []; last = {}
    for i, s, t in zip(g.index, g.s, g.t):
        if t - last.get(s, -1e18) >= h * 3600: keep.append(i); last[s] = t
    return g.loc[keep]
res = []
for xr, run, bmin, mv, col in itertools.product((1.5, 2, 3), (2, 6, 12), (0, 1e6), (0, 0.05, 0.10, 0.15), ("S_10_25", "S_7_20", "S_10_10")):
    g = dedup(S[(S.x >= xr) & (S.run_h >= run) & (S.bor >= bmin) & (S.dr >= 20e3) & (S.c_r24.abs() >= mv)])
    h1, h2 = g[g.half == 1], g[g.half == 2]
    if len(h1) < 30: continue
    res.append(dict(xr=xr, run=run, bmin=bmin, mv=mv, col=col, n1=len(h1), m1=h1[col].mean(), wr1=(h1[col] > 0).mean(), n2=len(h2), m2=h2[col].mean(), wr2=(h2[col] > 0).mean()))
R = pd.DataFrame(res).sort_values("m1", ascending=False)
print("вариантов:", len(R)); print("10 лучших по 1-й половине и их 2-я половина:")
print(R.head(10).round(4).to_string(index=False))
top = R.head(20); print(f"20 лучших: 1-я пол. {top.m1.mean()*100:+.2f}%, 2-я пол. {top.m2.mean()*100:+.2f}% (в плюсе на 2-й {(top.m2 > 0).mean():.0%})")
print(f"все варианты: 1-я {R.m1.mean()*100:+.2f}%, 2-я {R.m2.mean()*100:+.2f}%")
bh2 = B[B.half == 2]; print(f"база 2-я половина: S_10_25 {bh2.S_10_25.mean()*100:+.2f}%, S_7_20 {bh2.S_7_20.mean()*100:+.2f}%, S_10_10 {bh2.S_10_10.mean()*100:+.2f}%; "
                           f"при |сутки| ≥ 10%: {bh2[bh2.c_r24.abs() >= 0.10].S_10_25.mean()*100:+.2f}% ({(bh2.c_r24.abs() >= 0.10).sum()})")
