"""Bitkub → общий формат: для каждого фьючерса с парой к бату — объём пары в $ на 15-мин сетке фьючерса (0, если сделок не было)."""
import pickle, re, glob, os
import numpy as np
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
K = pickle.load(open("s2/k2y.pkl", "rb"))
U = np.load("s4/bitkub/USDT.npy"); U[:, 0] = U[:, 0] // 900 * 900
fx_t, fx_c = U[:, 0], U[:, 4]
TH = {}
for s, a in K.items():
    fn = f"s4/bitkub/{strip(s)}.npy"
    if not os.path.exists(fn): continue
    b = np.load(fn)
    if len(b) < 50: continue
    b[:, 0] = b[:, 0] // 900 * 900
    usd = b[:, 5] * b[:, 1:5].mean(axis=1) / np.interp(b[:, 0], fx_t, fx_c)
    t = a["t"]; v = np.zeros(len(t)); idx = np.searchsorted(t, b[:, 0]); ok = idx < len(t); ok[ok] &= t[idx[ok]] == b[ok, 0]
    np.add.at(v, idx[ok], usd[ok]); TH[s] = (v, float(b[0, 0]))
pickle.dump(TH, open("s4/thai.pkl", "wb")); print("фьючерсов с парой к бату:", len(TH))
