import time, numpy as np, pandas as pd
from search import D, stats, TRAIN_END, bar
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 300)
v = {c: D[c].values for c in D.columns if D[c].dtype != object}
BASES = {
 "P1 текущее пр.1 (4ч +8…17, серия≥4)": (v["run_h"] >= 4) & (v["ch_4h"] >= 8) & (v["ch_4h"] <= 17),
 "P2 памп 24ч +2…10, серия≥1, B/R≥5": (v["run_h"] >= 1) & (v["ch_24h"] >= 2) & (v["ch_24h"] <= 10) & (v["br"] >= 5),
 "P3 памп 2ч +6…21, серия≥1, B/R≥10": (v["run_h"] >= 1) & (v["ch_2h"] >= 6) & (v["ch_2h"] <= 21) & (v["br"] >= 10),
 "D1 текущее пр.2 (4ч −8…−17, серия≥4, B/R≥5)": (v["run_h"] >= 4) & (v["ch_4h"] <= -8) & (v["ch_4h"] >= -17) & (v["br"] >= 5),
 "D2 слив 12ч ≤−4, серия≥6, B/R≥10": (v["run_h"] >= 6) & (v["ch_12h"] <= -4) & (v["br"] >= 10),
 "D3 слив 8ч ≤−4, серия≥3, B/R≥30": (v["run_h"] >= 3) & (v["ch_8h"] <= -4) & (v["br"] >= 30),
}
FEATS = ["from_high24", "from_low24", "from_high4h", "from_low4h", "rise_before", "vol24", "vrel_1h", "vrel_4h", "tbuy_1h", "qv24_m",
         "f_h", "f_per", "f_24h", "btc_24h", "btc_7d", "btc_30d", "breadth", "alt7", "bor_g", "run_posts", "run_h", "bor", "rep", "br",
         "pos", "ncoins", "hour", "ch_1h", "ch_4h", "ch_12h", "ch_24h", "ch_3d", "ch_7d"]
tr = bar < TRAIN_END
rows = []; t0 = time.time()
for bname, bm in BASES.items():
    for tp, sl in ((10, 20), (15, 25)):
        b = stats(bm, tp, sl)
        base = dict(base=bname, ex=f"{tp}/{sl}", filt="— без фильтра —", n_tr=b["train"]["n"], m_tr=b["train"]["mean"], s_tr=b["train"]["sum"],
                    min_tr=b["segs"][:4].min(), pos_tr=int((b["segs"][:4] > 0).sum()), n_te=b["test"]["n"], m_te=b["test"]["mean"], s_te=b["test"]["sum"],
                    pos_te=int((b["segs"][4:] > 0).sum()), segs=np.round(b["segs"], 1))
        rows.append(base)
        for f in FEATS:
            x = v[f]; qs = np.nanquantile(x[bm & tr], [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
            for q, qv in zip((10, 20, 30, 40, 50, 60, 70, 80, 90), qs):
                for side in (">", "<"):
                    keep = bm & ((x > qv) if side == ">" else (x < qv))
                    r = stats(keep, tp, sl)
                    if r["train"]["n"] < 80: continue
                    rows.append(dict(base=bname, ex=f"{tp}/{sl}", filt=f"{f} {side} {qv:.4g} (q{q})", feat=f, side=side, q=q,
                                     n_tr=r["train"]["n"], m_tr=r["train"]["mean"], s_tr=r["train"]["sum"], min_tr=r["segs"][:4].min(),
                                     pos_tr=int((r["segs"][:4] > 0).sum()), n_te=r["test"]["n"], m_te=r["test"]["mean"], s_te=r["test"]["sum"],
                                     pos_te=int((r["segs"][4:] > 0).sum()), segs=np.round(r["segs"], 1)))
    print(bname, f"{time.time() - t0:.0f} с", flush=True)
R = pd.DataFrame(rows); R.to_pickle("phase2.pkl"); print("готово", len(R))
