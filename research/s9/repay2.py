import numpy as np, pandas as pd
S = pd.read_pickle("s9/repay_cand.pkl"); B = pd.read_pickle("s9/repay_base.pkl")
def dedup(g, h=24):
    g = g.sort_values("t"); keep = []; last = {}
    for i, s, t in zip(g.index, g.s, g.t):
        if t - last.get(s, -1e18) >= h * 3600: keep.append(i); last[s] = t
    return g.loc[keep]
R = dedup(S[(S.x >= 2) & (S.run_h >= 6) & (S.dr >= 20e3)])
COLS = ["S_10_25", "S_10_10", "S_7_20"]
def show(nm, g, base=None):
    if len(g) < 20: return
    h1, h2 = g[g.half == 1], g[g.half == 2]
    print(f"{nm:46s} n={len(g):4d} WR {(g.S_10_25 > 0).mean():.0%} | " + " ".join(f"{c}: {g[c].mean()*100:+.2f} ({h1[c].mean()*100:+.2f}/{h2[c].mean()*100:+.2f})" for c in COLS)
          + (f" | база {base[COLS[0]].mean()*100:+.2f} ({len(base)})" if base is not None else ""))
print("REPAY ×2, серия ≥ 6 ч:", len(R))
for nm, m, mb in (("все", R.s == R.s, B.s == B.s),
                  ("за 4 ч ≥ +8% (как правило 1 бота)", R.c_r4 >= 0.08, B.c_r4 >= 0.08),
                  ("за 4 ч ≤ −8% (как правило 2 бота)", R.c_r4 <= -0.08, B.c_r4 <= -0.08),
                  ("за 4 ч в ±8%", R.c_r4.abs() < 0.08, B.c_r4.abs() < 0.08),
                  ("за сутки ≥ +10%", R.c_r24 >= 0.10, B.c_r24 >= 0.10), ("за сутки ≤ −10%", R.c_r24 <= -0.10, B.c_r24 <= -0.10),
                  ("за сутки ±10%", R.c_r24.abs() < 0.10, B.c_r24.abs() < 0.10),
                  ("BOR ≥ 1 млн", R.bor >= 1e6, B.bor >= 1e6), ("BOR < 1 млн", R.bor < 1e6, B.bor < 1e6),
                  ("BOR тоже вырос за час (≥ ×1,2)", R.db >= 1.2, None), ("BOR не вырос (< ×1,2)", R.db < 1.2, None),
                  ("фандинг < 0", R.c_f_last < 0, B.c_f_last < 0), ("фандинг ≥ 0", R.c_f_last >= 0, B.c_f_last >= 0),
                  ("покупки тейкеров 4 ч < 50%", R.c_tb4 < 0.5, B.c_tb4 < 0.5), ("покупки тейкеров 4 ч ≥ 50%", R.c_tb4 >= 0.5, B.c_tb4 >= 0.5)):
    show(nm, R[m], B[mb] if mb is not None else None)
print("по кварталам (S_10_25, на сделку):"); print(R.groupby("q").S_10_25.agg(["size", "mean"]).round(4).T.to_string())
print("отдача/займ (REP/BOR) в момент события: медиана", (R.rep / R.bor).median().round(3), "у базы", (B.rep / B.bor).median().round(3))
