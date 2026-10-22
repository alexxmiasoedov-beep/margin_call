"""Контроль: все моменты «за сутки ≤ −10%» (закрытие 15-мин свечи, одна точка на монету за 24 ч) в период канала (20.02.2025–18.10.2026);
есть ли монета в этот момент в маржинальном канале (пост за последние 30 мин) и появилась ли недавно. Исходы — как в md_events."""
import pickle, re, sys
import numpy as np, pandas as pd
sys.argv = ["x"]
exec(open("s9/md_events.py").read().split("# 15-мин сетка постов канала")[0])
T0, T1 = PT[0] + 7 * 86400, PT[-1] - 2 * 86400
inv = {}
for c0, arr in G.items():
    s = sym_of.get(c0) or sym_of.get(strip(c0))
    if s: inv[s] = arr[:, 0]
rows = []
for s, a in K.items():
    t = a["t"]; c = a["c"].astype(np.float64)
    if len(t) < 400: continue
    r24 = np.full(len(c), np.nan); r24[96:] = c[96:] / c[:-96] - 1
    cand = np.flatnonzero((r24 <= -0.10) & (t + 900 >= T0) & (t + 900 <= T1))
    last = -10**9
    for j in cand:
        if j - last < 96: continue
        last = j; T = t[j] + 900; tt = inv.get(s)
        inn = enter = 0
        if tt is not None:
            k = np.searchsorted(tt, T, "right") - 1
            if k >= 0 and T - tt[k] <= 1800:
                inn = 1
                # непрерывная серия: первый пост серии
                kk = k
                while kk > 0 and tt[kk] - tt[kk - 1] <= 30 * 60: kk -= 1
                enter = int(T - tt[kk] <= 6 * 3600)
        cx = ctx(s, j)
        if cx is None: continue
        o = outcomes(s, j)
        if o is None: continue
        rows.append(dict(s=s, t=float(T), j=int(j), inn=inn, enter6=enter, **{f"c_{k}": v for k, v in cx.items()}, **o))
B = pd.DataFrame(rows); B["half"] = np.where(B.t < CUT, 1, 2); B.to_pickle("s9/base_drop.pkl")
COLS = ["L_10_10", "L_20_10", "L_30_15", "S_10_25"]
for nm, g in (("все падения ≤ −10% за сутки", B), ("монеты нет в канале", B[B.inn == 0]), ("монета в канале", B[B.inn == 1]),
              ("в канале, серия ≤ 6 ч (недавно вошла)", B[B.enter6 == 1])):
    h1, h2 = g[g.half == 1], g[g.half == 2]
    print(f"{nm:40s} n={len(g):6d} r48 {g.r48.mean()*100:+.2f}% | " + " ".join(f"{c}: {g[c].mean()*100:+.2f} ({h1[c].mean()*100:+.2f}/{h2[c].mean()*100:+.2f})" for c in COLS))
