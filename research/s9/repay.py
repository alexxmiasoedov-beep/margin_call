"""Шорт после всплеска отдачи (REPAY) против базы «монета в канале ≥ 6 ч» (случайные моменты серии, одна точка на монету за 24 ч),
чувствительность к порогам, по кварталам, пересечение с правилами бота (рост/падение 8–17% за 4 ч)."""
import pickle, re, sys
import numpy as np, pandas as pd
exec(open("s9/md_events.py").read().split("# 15-мин сетка постов канала")[0])
rng = np.random.default_rng(7)
ev, base = [], []
for c0, arr in G.items():
    s = sym_of.get(c0) or sym_of.get(strip(c0))
    if s is None or s not in K: continue
    t = K[s]["t"]; tt, bor, rep, br = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3]
    # серии (разрыв > 30 мин — новая серия)
    br_idx = np.r_[0, np.flatnonzero(np.diff(tt) > 30 * 60) + 1]; ends = np.r_[br_idx[1:] - 1, len(tt) - 1]
    for st, en in zip(br_idx, ends):
        T0 = tt[st]
        # база: случайный пост серии после ≥ 6 ч, не чаще раза в 24 ч
        idx = np.flatnonzero(tt[st:en + 1] - T0 >= 6 * 3600) + st
        last = -1e18
        for i in rng.permutation(idx)[:max(1, len(idx) // 288)]:
            if tt[i] - last >= 86400: base.append((s, tt[i], bor[i], rep[i], (tt[i] - T0) / 3600)); last = tt[i]
        # события отдачи внутри серии: REP вырос в ≥ X раз за час
        for i in range(st, en + 1):
            if tt[i] - T0 < 2 * 3600: continue
            k = np.searchsorted(tt, tt[i] - 3600, "right") - 1
            if k < st or tt[i] - tt[k] > 75 * 60: continue
            ev.append((s, tt[i], bor[i], rep[i], rep[k], bor[k], (tt[i] - T0) / 3600))
EV = pd.DataFrame(ev, columns=["s", "t", "bor", "rep", "rep1", "bor1", "run_h"]); BS = pd.DataFrame(base, columns=["s", "t", "bor", "rep", "run_h"])
EV["x"] = EV.rep / EV.rep1.clip(lower=1); EV["dr"] = EV.rep - EV.rep1; EV["db"] = EV.bor / EV.bor1.clip(lower=1)
print("кандидатов (все посты серий ≥ 2 ч):", len(EV), "база:", len(BS))
def add_out(df):
    out = []
    for x in df.itertuples():
        a = K[x.s]; j = int(np.searchsorted(a["t"], x.t, "right") - 1)
        if j < 300 or j >= len(a["t"]) - 2: out.append(None); continue
        o = outcomes(x.s, j); c = ctx(x.s, j)
        out.append(None if (o is None or c is None) else {**o, **{f"c_{k}": v for k, v in c.items()}, "j": j})
    ok = [o is not None for o in out]; df = df[ok].copy(); X = pd.DataFrame([o for o in out if o is not None], index=df.index)
    df = pd.concat([df, X], axis=1); df["half"] = np.where(df.t < CUT, 1, 2); df["q"] = pd.to_datetime(df.t, unit="s").dt.to_period("Q").astype(str); return df
def dedup(g, h=24):
    g = g.sort_values("t"); keep = []; last = {}
    for i, s, t in zip(g.index, g.s, g.t):
        if t - last.get(s, -1e18) >= h * 3600: keep.append(i); last[s] = t
    return g.loc[keep]
BS = add_out(BS)
SEL = EV[(EV.x >= 1.5) & (EV.dr >= 10e3)]
SEL = add_out(dedup(SEL, 1))      # пока все кандидаты с x ≥ 1,5, дедуп позже по варианту
SEL.to_pickle("s9/repay_cand.pkl"); BS.to_pickle("s9/repay_base.pkl")
COLS = ["S_10_25", "S_10_10", "S_7_20", "S_5_25", "L_10_10"]
def show(nm, g):
    if len(g) < 25: return
    h1, h2 = g[g.half == 1], g[g.half == 2]
    print(f"{nm:52s} n={len(g):5d} WR(S10_25) {(g.S_10_25 > 0).mean():.0%} r24 {g.r24.mean()*100:+.2f}% | " +
          " ".join(f"{c}: {g[c].mean()*100:+.2f} ({h1[c].mean()*100:+.2f}/{h2[c].mean()*100:+.2f})" for c in COLS))
show("БАЗА: в канале ≥ 6 ч, случайный момент", BS)
show("БАЗА, BOR ≥ 1 млн", BS[BS.bor >= 1e6])
for xr in (1.5, 2, 3, 5):
    for run in (2, 6, 12):
        for bmin in (0, 1e6):
            g = dedup(SEL[(SEL.x >= xr) & (SEL.run_h >= run) & (SEL.bor >= bmin) & (SEL.dr >= 20e3)])
            show(f"отдача ×{xr:g} за час, серия ≥ {run} ч, BOR ≥ {bmin/1e6:g} млн", g)
