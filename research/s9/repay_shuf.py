"""Контроль к repay_honest.py: та же процедура отбора (183 варианта), но исходы перемешаны внутри месяца между кандидатами — 20 прогонов."""
import itertools
import numpy as np, pandas as pd
S0 = pd.read_pickle("s9/repay_cand.pkl")
def dedup(g, h=24):
    g = g.sort_values("t"); keep = []; last = {}
    for i, s, t in zip(g.index, g.s, g.t):
        if t - last.get(s, -1e18) >= h * 3600: keep.append(i); last[s] = t
    return g.loc[keep]
OUT = ["S_10_25", "S_7_20", "S_10_10"]
def run(S):
    res = []
    for xr, run_, bmin, mv, col in itertools.product((1.5, 2, 3), (2, 6, 12), (0, 1e6), (0, 0.05, 0.10, 0.15), OUT):
        g = dedup(S[(S.x >= xr) & (S.run_h >= run_) & (S.bor >= bmin) & (S.dr >= 20e3) & (S.c_r24.abs() >= mv)])
        h1, h2 = g[g.half == 1], g[g.half == 2]
        if len(h1) < 30: continue
        res.append((h1[col].mean(), h2[col].mean()))
    R = pd.DataFrame(res, columns=["m1", "m2"]).sort_values("m1", ascending=False)
    return R.head(20).m1.mean(), R.head(20).m2.mean(), R.head(1).m2.iloc[0]
print("настоящие: топ-20 1-я %.2f%% → 2-я %.2f%%, лучший → %.2f%%" % tuple(100 * v for v in run(S0)))
rng = np.random.default_rng(5); S0["m"] = pd.to_datetime(S0.t, unit="s").dt.strftime("%y%m")
out = []
for k in range(20):
    S = S0.copy()
    for mm, idx in S.groupby("m").groups.items():
        idx = np.array(list(idx)); S.loc[idx, OUT] = S0.loc[rng.permutation(idx), OUT].values
    out.append(run(S))
O = pd.DataFrame(out, columns=["top20_1", "top20_2", "best_2"]) * 100
print("перемешанные (20 прогонов): топ-20 2-я половина: среднее %.2f%%, макс %.2f%%; лучший вариант 2-я: среднее %.2f%%, макс %.2f%%"
      % (O.top20_2.mean(), O.top20_2.max(), O.best_2.mean(), O.best_2.max()))
