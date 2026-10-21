"""Разворот после пампа: какие признаки отличают момент, после которого будет −15% за 24 ч, от момента без такого падения."""
import pickle, datetime, os
import numpy as np, scipy.stats as st
MSK = datetime.timezone(datetime.timedelta(hours=3))
F = pickle.load(open("mm2/rev_feats.pkl", "rb")); R = {(r["s"], r["i"]): r for r in pickle.load(open("mm2/rev_moments.pkl", "rb"))}
for f in F: f.update({k: v for k, v in R[(f["s"], f["i"])].items() if k in ("since_h", "pump_gain", "gain_now", "from_peak", "h_since_peak", "fwd_min", "fwd_max", "ev")})
MID = datetime.datetime(2026, 10, 4, tzinfo=MSK).timestamp()
def auc(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float); a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 30 or len(b) < 30: return np.nan
    rk = st.rankdata(np.concatenate([a, b])); return (rk[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))
keys = sorted({k for r in F for k in r if k not in ("g", "s", "i", "t0", "ev", "fwd_min", "fwd_max")})
val = lambda rows, k: [r.get(k, np.nan) for r in rows]
Y = [r for r in F if r["g"] == "rev"]; N = [r for r in F if r["g"] == "norev"]
out = []
for k in keys:
    a, b = val(Y, k), val(N, k); n = (int(np.isfinite(np.asarray(a, float)).sum()), int(np.isfinite(np.asarray(b, float)).sum()))
    h = [auc(val([r for r in Y if (r["t0"] < MID) == (j == 0)], k), val([r for r in N if (r["t0"] < MID) == (j == 0)], k)) for j in (0, 1)]
    out.append((k, n, np.nanmedian(np.asarray(a, float)), np.nanmedian(np.asarray(b, float)), auc(a, b), h))
print(f"{'признак':16s} {'n разв/нет':>12s} | медиана разворот / нет | AUC (1-я пол., 2-я пол.)")
for k, n, ma, mb, au, h in sorted(out, key=lambda x: -abs((x[4] if np.isfinite(x[4]) else 0.5) - 0.5)):
    print(f"{k:16s} {n[0]:5d}/{n[1]:5d} | {ma:9.4g} {mb:9.4g} | {au:5.2f} ({h[0]:.2f}, {h[1]:.2f})")
