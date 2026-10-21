"""Какие признаки отличают момент перед пампом / дампом от покоя и — главное — памп от дампа (направление)."""
import pickle, datetime, sys, os
import numpy as np
MSK = datetime.timezone(datetime.timedelta(hours=3))
R = pickle.load(open(os.environ.get("IN", "mm2/feats.pkl"), "rb"))
MID = datetime.datetime(2026, 10, 4, tzinfo=MSK).timestamp()
def auc(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float); a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 15 or len(b) < 15: return np.nan
    allv = np.concatenate([a, b]); rk = allv.argsort(kind="stable").argsort() + 1.0
    # средние ранги для равных значений
    import scipy.stats as st
    rk = st.rankdata(allv)
    return (rk[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))
keys = sorted({k for r in R for k in r if k not in ("g", "s", "i", "t0")})
G = {g: [r for r in R if r["g"] == g] for g in ("памп", "дамп", "покой")}
val = lambda rows, k: [r.get(k, np.nan) for r in rows]
half = lambda rows, h: [r for r in rows if (r["t0"] < MID) == (h == 0)]
out = []
for k in keys:
    P, D, C = (val(G[g], k) for g in ("памп", "дамп", "покой"))
    n = [int(np.isfinite(np.asarray(x, float)).sum()) for x in (P, D, C)]
    pd_ = auc(P, D); pc = auc(P, C); dc = auc(D, C)
    h = [auc(val(half(G["памп"], j), k), val(half(G["дамп"], j), k)) for j in (0, 1)]
    out.append((k, n, np.nanmedian(np.asarray(P, float)), np.nanmedian(np.asarray(D, float)), np.nanmedian(np.asarray(C, float)), pc, dc, pd_, h))
print(f"{'признак':16s} {'n П/Д/П':>15s} | медиана памп / дамп / покой | AUC памп-покой  дамп-покой | ПАМП-ДАМП (1-я пол., 2-я пол.)")
for k, n, mp_, md, mc, pc, dc, pd_, h in sorted(out, key=lambda x: -abs((x[7] if np.isfinite(x[7]) else 0.5) - 0.5)):
    print(f"{k:16s} {n[0]:4d}/{n[1]:3d}/{n[2]:4d} | {mp_:9.4g} {md:9.4g} {mc:9.4g} | {pc:5.2f} {dc:5.2f} | {pd_:5.2f} ({h[0]:.2f}, {h[1]:.2f})")
