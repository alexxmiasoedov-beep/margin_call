"""Первый взгляд: события MarginData × признаки займа (s10/ev_margin.pkl). Дедуп 24 ч по монете внутри типа события."""
import numpy as np, pandas as pd
E = pd.read_pickle("s9/md_events.pkl"); M = pd.read_pickle("s10/ev_margin.pkl")
D = E.merge(M.drop(columns=[c for c in M.columns if c in ("c_v24",)]), on=["s", "t"], how="left")
for c in ("bdz", "bd_1h", "chng", "cex_3d", "bz", "bor_vol", "mkt_bz"):
    if c not in D: D[c] = np.nan
def dedup(g, h=24):
    g = g.sort_values("t"); keep = []; last = {}
    for i, s, t in zip(g.index, g.s, g.t):
        if t - last.get(s, -1e18) >= h * 3600: keep.append(i); last[s] = t
    return g.loc[keep]
OUT = ["S_10_25", "S_7_20", "L_10_10", "L_20_10", "L_30_15"]
def show(nm, g):
    g = dedup(g)
    if len(g) < 30: print(f"{nm:58s} n={len(g)}"); return
    h1, h2 = g[g.half == 1], g[g.half == 2]
    print(f"{nm:58s} n={len(g):5d} " + " ".join(f"{c} {g[c].mean()*100:+.2f}" for c in OUT)
          + f" | S_10_25 1-я {h1.S_10_25.mean()*100:+.2f} 2-я {h2.S_10_25.mean()*100:+.2f} | L_20_10 {h1.L_20_10.mean()*100:+.2f}/{h2.L_20_10.mean()*100:+.2f}")
for ev in ("ENTER", "JUMP"):
    g0 = D[D.ev == ev]; print(f"\n=== {ev}")
    show("все", g0)
    for lo, hi in ((0, 0.02), (0.02, 0.1), (0.1, 0.5), (0.5, 99)):
        show(f"займ к объёму фьючерса {lo}…{hi}", g0[(g0.bor_vol >= lo) & (g0.bor_vol < hi)])
    for lo, hi in ((-9, 0), (0, 2), (2, 4), (4, 99)):
        show(f"B.Z {lo}…{hi}", g0[(g0.bz >= lo) & (g0.bz < hi)])
    show("BΔZ ≥ 2", g0[g0.bdz >= 2])
    for lo, hi in ((-9, -0.5), (-0.5, 0.5), (0.5, 1.5), (1.5, 99)):
        show(f"фон: z суммарного займа альтов {lo}…{hi}", g0[(g0.mkt_bz >= lo) & (g0.mkt_bz < hi)])
    show("ончейн-приток за 3 дня ≥ +3%", g0[g0.cex_3d >= 0.03]); show("ончейн-отток за 3 дня ≤ −3%", g0[g0.cex_3d <= -0.03])
    flat = (g0.c_rng48 <= 0.12)
    show("«пул»: флэт 48 ч ≤ 12% + B.Z ≥ 2", g0[flat & (g0.bz >= 2)])
    show("«пул»: флэт + B.Z ≥ 2 + фандинг −0,03…0%/8ч", g0[flat & (g0.bz >= 2) & (g0.c_f_last < 0) & (g0.c_f_last > -0.0003)])
    show("«пул»: флэт + B.Z ≥ 2 + фандинг < 0 + тейкеры 24 ч > 52%", g0[flat & (g0.bz >= 2) & (g0.c_f_last < 0) & (g0.c_tb24 > 0.52)])
    show("«пул»: флэт + займ/объём ≥ 0,1 + фандинг < 0", g0[flat & (g0.bor_vol >= 0.1) & (g0.c_f_last < 0)])
