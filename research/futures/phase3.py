"""Большая сетка «сигнал × фильтры × выход» с результатом по 7 кварталам → phase3.pkl (для проверки «по фазам вслепую»)."""
import time, itertools, pickle, numpy as np
import search as S
v = {c: S.D[c].values for c in S.D.columns if S.D[c].dtype != object}
NSEG = len(S.SEG)
def seg_stats(mask, tp, sl):
    sel, pnl, st, tk, fu = S.trades(mask, tp, sl)
    sid = S.seg_id[sel]; p = pnl[sel]
    return np.bincount(sid, weights=p, minlength=NSEG), np.bincount(sid, minlength=NSEG), np.bincount(sid, weights=p * p, minlength=NSEG)
EX = ((6, 20), (10, 20), (15, 25))
out = []; t0 = time.time()
W = ("1h", "2h", "4h", "8h", "12h", "24h")
BANDS = [(lo, hi) for lo in (2, 4, 6, 8, 10, 12, 15) for hi in (lo + 8, lo + 15, 1000)]
nan0 = lambda x: np.nan_to_num(x, nan=-1e9)
# ---- пампы
fh4 = {0: np.ones(len(S.D), bool), 1: nan0(-v["from_high4h"]) >= 1, 2: nan0(-v["from_high4h"]) >= 2, 4: nan0(-v["from_high4h"]) >= 4}
btcf = {"любой": np.ones(len(S.D), bool), "BTC за 30д < 0": nan0(-v["btc_30d"]) > 0}
liq = {0: np.ones(len(S.D), bool), 5: nan0(v["qv24_m"]) >= 5, 20: nan0(v["qv24_m"]) >= 20}
for w in W:
    x = v[f"ch_{w}"]
    for lo, hi in BANDS:
        mp = (x >= lo) & (x <= hi)
        if mp.sum() < 500: continue
        for rm in (1, 2, 4, 8):
            m1 = mp & (v["run_h"] >= rm)
            for b in (0, 5, 10, 30):
                m2 = m1 & (v["br"] >= b)
                for fk, fm in fh4.items():
                    m3 = m2 & fm
                    for bk, bm in btcf.items():
                        m4 = m3 & bm
                        for lk, lm in liq.items():
                            m = m4 & lm
                            if m.sum() < 300: continue
                            for tp, sl in EX:
                                s, n, ss = seg_stats(m, tp, sl)
                                out.append(("pump", w, lo, hi, rm, b, fk, bk, lk, tp, sl, s, n, ss))
    print("pump", w, len(out), f"{time.time() - t0:.0f} с", flush=True)
# ---- сливы
btc24 = {"любой": np.ones(len(S.D), bool), "BTC 24ч > −1%": nan0(v["btc_24h"]) > -1, "BTC 24ч > 0": nan0(v["btc_24h"]) > 0, "BTC 24ч > +1%": nan0(v["btc_24h"]) > 1}
for w in W:
    x = v[f"ch_{w}"]
    for lo, hi in BANDS:
        mp = (x <= -lo) & (x >= -hi)
        if mp.sum() < 500: continue
        for rm in (1, 2, 4, 8):
            m1 = mp & (v["run_h"] >= rm)
            for b in (0, 5, 10, 30, 60):
                m2 = m1 & (v["br"] >= b)
                for bk, bm in btc24.items():
                    m4 = m2 & bm
                    for lk, lm in liq.items():
                        m = m4 & lm
                        if m.sum() < 300: continue
                        for tp, sl in EX:
                            s, n, ss = seg_stats(m, tp, sl)
                            out.append(("dump", w, lo, hi, rm, b, 0, bk, lk, tp, sl, s, n, ss))
    print("dump", w, len(out), f"{time.time() - t0:.0f} с", flush=True)
pickle.dump(out, open("phase3.pkl", "wb")); print("готово", len(out))
