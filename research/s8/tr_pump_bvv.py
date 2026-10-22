"""Пампы (+15% за ≤ 2 ч из покоя) с долей лиры ≥ 10% — по всплеску доли Bitvavo, отдельно с корейским сигналом и без;
пересечение с журналом 🇹🇷 (сделка той же монеты в ±4 ч по бэктесту rush_wb.py)."""
import pickle
import numpy as np, pandas as pd
D = pd.read_pickle("s6/feat.pkl"); B = pd.read_pickle("s5/pump_bvv.pkl"); A = pickle.load(open("s8/rush_wb.pkl", "rb"))["A"]
D["q"] = pd.to_datetime(D.t, unit="s").dt.to_period("Q").astype(str)
T = D.merge(B[["s", "t", "has", "x", "fshare", "fhas"]].rename(columns={"fshare": "fs", "fhas": "fh"}), on=["s", "t"], how="inner")
T = T[(T.fh == True) & (T.fs >= 0.1) & (T.has == True)].copy(); T["kr"] = T.kshare >= 0.2
def st(nm, g, col):
    y1, y2 = g[g.y == 1], g[g.y == 2]; qm = g.groupby("q")[col].mean()
    print(f"  {nm:10s} {len(g):4d} WR {(g[col] > 0).mean():.1%} {g[col].mean() * 100:+.2f}% (1-й {len(y1)} {y1[col].mean() * 100:+.2f}, "
          f"2-й {len(y2)} {y2[col].mean() * 100:+.2f}), кв. {(qm > 0).sum()}/{len(qm)}")
for col in ("S_10_25", "S_7_20"):
    for kr in (True, False):
        g = T[T.kr == kr]; print(col, "корейский сигнал" if kr else "без корейского сигнала")
        st("× 0–2", g[g.x < 2], col); st("× 2–4", g[(g.x >= 2) & (g.x < 4)], col); st("× ≥ 4", g[g.x >= 4], col)
g = T[~T.kr]
print(pd.concat([g[g.x >= 4].groupby("q").S_10_25.agg(["size", "mean"]), g[g.x < 4].groupby("q").S_10_25.agg(["size", "mean"])], axis=1, keys=["×≥4", "×<4"]).round(4).to_string())
R = A.groupby("s").t.apply(np.array).to_dict()
def near(s, t, w=4 * 3600):
    r = R.get(s)
    if r is None: return np.nan
    d = r - t; k = np.flatnonzero(np.abs(d) <= w); return d[k[0]] if len(k) else np.nan
g = g.assign(dt=[near(s, t) for s, t in zip(g.s, g.t)])
for nm, h in (("× ≥ 4", g[g.x >= 4]), ("× < 4", g[g.x < 4])):
    ov = h.dt.notna()
    print(f"{nm}: {len(h)} пампов, у 🇹🇷 сделка той же монеты в ±4 ч: {ov.sum()} ({ov.mean():.0%}); шорт 10/25 с пересечением "
          f"{h[ov].S_10_25.mean() * 100:+.2f}%, без {h[~ov].S_10_25.mean() * 100:+.2f}% ({(~ov).sum()})")
