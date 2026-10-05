import time, pickle, numpy as np, pandas as pd
from search import D, stats, fmt, SEG
t0 = time.time()
run_h = D.run_h.values; br = D.br.values
ch = {w: D[f"ch_{w}"].values for w in ("1h", "2h", "4h", "8h", "12h", "24h")}
def rec(d, w, lo, hi, rm, b, tp, sl, hold, r):
    segs = r["segs"]
    return dict(dir=d, w=w, lo=lo, hi=hi, run=rm, br=b, tp=tp, sl=sl, hold=hold,
                n_tr=r["train"]["n"], sum_tr=r["train"]["sum"], mean_tr=r["train"]["mean"], t_tr=r["train"]["t"],
                pos_tr=int((segs[:4] > 0).sum()), min_tr=segs[:4].min(),
                n_te=r["test"]["n"], sum_te=r["test"]["sum"], mean_te=r["test"]["mean"], t_te=r["test"]["t"],
                pos_te=int((segs[4:] > 0).sum()), dd=r["dd"], **{f"s{k}": v for k, v in enumerate(segs)})
# база: текущие правила бота
r1 = (run_h >= 4) & (ch["4h"] >= 8) & (ch["4h"] <= 17); r2 = (run_h >= 4) & (ch["4h"] <= -8) & (ch["4h"] >= -17) & (br >= 5)
for lab, m in (("ТЕКУЩИЕ правила 1+2", r1 | r2), ("текущее правило 1", r1), ("текущее правило 2", r2)):
    for tp, sl in ((6, 20), (15, 25)):
        print(f"{lab:22s} {tp}/{sl}: " + fmt(stats(m, tp, sl)), flush=True)
res = []
for d in ("pump", "dump"):
    for w, x in ch.items():
        for lo in (2, 4, 6, 8, 10, 12, 15, 20, 30):
            for hi in (lo + 4, lo + 8, lo + 15, 1000):
                mp = ((x >= lo) & (x <= hi)) if d == "pump" else ((x <= -lo) & (x >= -hi))
                if mp.sum() < 300: continue
                for rm in (1, 2, 3, 4, 6, 8, 12):
                    m1 = mp & (run_h >= rm)
                    for b in (0, 2, 5, 10, 30):
                        m = m1 & (br >= b)
                        if m.sum() < 300: continue
                        for tp, sl, hold in ((6, 20, 192), (10, 20, 192), (15, 25, 192)):
                            res.append(rec(d, w, lo, hi, rm, b, tp, sl, hold, stats(m, tp, sl, hold)))
    print(d, "готово", len(res), f"{time.time() - t0:.0f} с", flush=True)
R = pd.DataFrame(res); R.to_pickle("phase1.pkl"); print("всего вариантов", len(R))
