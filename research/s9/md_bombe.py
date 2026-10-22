"""Перебор правил на событиях маржинального бота (ENTER / JUMP / REPAY / EXIT): условия — квинтили признаков (≤ / ≥), одиночные и пары;
отбор по 1-й половине (до 01.12.2025), проверка на 2-й; контроль — исходы, перемешанные внутри месяца."""
import sys, itertools
import numpy as np, pandas as pd
D = pd.read_pickle("s9/md_events.pkl")
def dedup(g, h=24):
    g = g.sort_values("t"); keep = []; last = {}
    for i, s, t in zip(g.index, g.s, g.t):
        if t - last.get(s, -1e18) >= h * 3600: keep.append(i); last[s] = t
    return g.loc[keep]
FEATS = ["c_r4", "c_r24", "c_r72", "c_rng24", "c_rng48", "c_vr", "c_tb4", "c_tb24", "c_f_last", "c_hi7", "bor", "br", "run_h", "btc24"]
OUTS = ["L_10_10", "L_20_10", "L_30_15", "S_10_25", "S_7_20", "S_10_10"]
rng = np.random.default_rng(1)
for ev in ("ENTER", "JUMP", "REPAY", "EXIT"):
    g = dedup(D[D.ev == ev]).reset_index(drop=True)
    g["m"] = pd.to_datetime(g.t, unit="s").dt.strftime("%y%m")
    h1 = (g.half == 1).values
    conds, names = [], []
    for f in FEATS:
        x = g[f].values.astype(float)
        if np.isnan(x).mean() > 0.5: continue
        qs = np.nanquantile(x[h1], [0.2, 0.4, 0.6, 0.8])
        for q in np.unique(qs):
            conds.append(x <= q); names.append(f"{f}≤{q:.3g}"); conds.append(x >= q); names.append(f"{f}≥{q:.3g}")
    C = np.array(conds, dtype=np.float64)                      # условия × события
    for shuf in (False, True):
        Y = g[OUTS].values.copy()
        if shuf:
            for mm, idx in g.groupby("m").groups.items():
                idx = np.array(list(idx)); Y[idx] = Y[rng.permutation(idx)]
        Y = np.nan_to_num(Y)
        best = []
        for k, o in enumerate(OUTS):
            y = Y[:, k]
            # пары: n и сумма на 1-й половине через матричное умножение
            A1 = C[:, h1]; n1 = A1 @ A1.T; s1 = (A1 * y[h1]) @ A1.T
            A2 = C[:, ~h1]; n2 = A2 @ A2.T; s2 = (A2 * y[~h1]) @ A2.T
            with np.errstate(invalid="ignore", divide="ignore"):
                m1 = np.where(n1 >= 40, s1 / n1, -9); m2 = np.where(n2 >= 1, s2 / np.maximum(n2, 1), np.nan)
            iu = np.triu_indices(len(C))
            flat = np.argsort(m1[iu])[::-1][:300]
            for f in flat:
                i, j = iu[0][f], iu[1][f]
                best.append((o, names[i], names[j], int(n1[i, j]), m1[i, j], int(n2[i, j]), m2[i, j]))
        B = pd.DataFrame(best, columns=["out", "c1", "c2", "n1", "m1", "n2", "m2"]).sort_values("m1", ascending=False)
        top = B.groupby("out").head(100)
        tag = "ПЕРЕМЕШАНО" if shuf else "настоящие"
        print(f"=== {ev} ({len(g)} событий), {tag}: топ-100 правил на каждый исход")
        print("   " + " | ".join(f"{o}: 1-я {top[top.out == o].m1.mean()*100:+.2f} → 2-я {top[top.out == o].m2.mean()*100:+.2f}" for o in OUTS))
        if not shuf:
            print(B.head(8).round(4).to_string(index=False))
