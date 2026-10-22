import numpy as np, pandas as pd, sys
D = pd.read_pickle("s9/md_events.pkl")
COLS = ["L_10_10", "L_20_10", "L_30_15", "S_10_10", "S_10_25", "S_7_20"]
def dedup(g, h=24):
    g = g.sort_values("t"); keep = []; last = {}
    for i, s, t in zip(g.index, g.s, g.t):
        if t - last.get(s, -1e18) >= h * 3600: keep.append(i); last[s] = t
    return g.loc[keep]
def row(nm, g):
    if len(g) < 30: return
    h1, h2 = g[g.half == 1], g[g.half == 2]
    cells = " ".join(f"{c[:1]}{c[2:]}:{g[c].mean()*100:+.2f}({h1[c].mean()*100:+.1f}/{h2[c].mean()*100:+.1f})" for c in COLS)
    print(f"{nm:44s} n={len(g):5d} r24 {g.r24.median()*100:+.1f}% r48 {g.r48.mean()*100:+.1f}% | {cells}")
for ev in ("ENTER", "JUMP", "REPAY", "EXIT"):
    g = dedup(D[D.ev == ev]); print(f"===== {ev}: {len(g)} (после дедупликации 24 ч)")
    row("все", g)
    row("BOR ≥ 1 млн $", g[g.bor >= 1e6]); row("BOR ≥ 5 млн $", g[g.bor >= 5e6])
    fl = (g.c_rng48 <= 0.10) & (g.c_r24.abs() <= 0.03)
    row("флэт (размах 48 ч ≤ 10%, за сутки ±3%)", g[fl]); row("флэт + BOR ≥ 1 млн", g[fl & (g.bor >= 1e6)])
    row("флэт + фандинг < 0", g[fl & (g.c_f_last < 0)]); row("флэт + фандинг ≤ −0,01%", g[fl & (g.c_f_last <= -0.0001)])
    row("после пампа: за сутки ≥ +20%", g[g.c_r24 >= 0.20]); row("после пампа: за 72 ч ≥ +50%", g[g.c_r72 >= 0.50])
    row("за 72 ч ≥ +50% и фандинг < 0", g[(g.c_r72 >= 0.50) & (g.c_f_last < 0)])
    row("после падения: за сутки ≤ −10%", g[g.c_r24 <= -0.10])
    row("покупки тейкеров 4 ч ≥ 55%", g[g.c_tb4 >= 0.55]); row("покупки тейкеров 4 ч ≤ 45%", g[g.c_tb4 <= 0.45])
