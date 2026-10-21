"""Дампы — зеркало пампов: −15% за ≤ 2 ч после 2 ч покоя (|цена/цена 2 ч назад − 1| ≤ 5%), первый за сутки, причинно.
19.10.2024–18.10.2026, все фьючерсы из архива (s2/k2y.pkl) → s7/dumps.pkl: (монета, время закрытия свечи-триггера, база, триггер)."""
import pickle, datetime
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as sw
K = pickle.load(open("s2/k2y.pkl", "rb"))
A = datetime.datetime(2024, 10, 19, tzinfo=datetime.timezone.utc).timestamp(); Z = datetime.datetime(2026, 10, 16, tzinfo=datetime.timezone.utc).timestamp()
def detect_down(c, l, thr=0.15):
    n = len(c); calm = np.zeros(n, bool); calm[8:] = np.abs(c[8:] / c[:-8] - 1) <= 0.05
    base = np.full(n, -1)
    for L in range(8, 0, -1):
        if n < L: continue
        rm = np.full(n, np.inf); rm[L - 1:] = sw(l, L).min(1)
        i = np.arange(n) - L; ic = np.clip(i, 0, n - 1)
        ok = (i >= 8) & calm[ic] & (rm <= c[ic] * (1 - thr)); base[ok] = i[ok]
    out, last = [], -10**9
    for j in np.flatnonzero(base >= 0):
        if j < 9 or j > n - 2 or j - last < 96: continue
        out.append((int(j), int(base[j]))); last = j
    return out
EV = []
for s, a in K.items():
    c = a["c"].astype(np.float64); l = a["l"].astype(np.float64)
    for j, i in detect_down(c, l):
        t = int(a["t"][j]) + 900
        if A <= t <= Z: EV.append(dict(s=s, t_in=t, jK=j, iK=i))
EV.sort(key=lambda e: e["t_in"]); pickle.dump(EV, open("s7/dumps.pkl", "wb"))
print("дампов", len(EV), "монет", len({e["s"] for e in EV}))
