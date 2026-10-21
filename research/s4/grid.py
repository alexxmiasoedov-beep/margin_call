"""Матрица 15-мин свечей всех фьючерсов на общей сетке времени: закрытие, максимум, минимум, объём ($)."""
import pickle, numpy as np
K = pickle.load(open("s2/k2y.pkl", "rb"))
syms = sorted(K); t0 = min(int(K[s]["t"][0]) for s in syms); t1 = max(int(K[s]["t"][-1]) for s in syms)
T = np.arange(t0, t1 + 900, 900, dtype=np.int64); n = len(T); m = len(syms); print(n, m)
out = {}
for f in ("c", "h", "l", "qv"):
    M = np.full((n, m), np.nan, dtype=np.float32)
    for k, s in enumerate(syms):
        a = K[s]; idx = (a["t"] - t0) // 900; M[idx, k] = a[f]
    out[f] = M
np.save("s4/T.npy", T); pickle.dump(syms, open("s4/syms.pkl", "wb"))
for f, M in out.items(): np.save(f"s4/G_{f}.npy", M)
