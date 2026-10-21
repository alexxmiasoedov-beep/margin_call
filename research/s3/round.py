"""Круглые числа: что делает цена после первого за сутки пересечения круглого уровня (m × 10^n) снизу вверх / сверху вниз —
против «фальшивых» уровней той же плотности (те же уровни × 1,0378). Закрытия 15-мин свечей, 2 года, монеты с объёмом ≥ 3 млн $ в сутки."""
import pickle, datetime, math
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as sw
K = pickle.load(open("s2/k2y.pkl", "rb"))
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
def levels(lo, hi, mant, shift):
    out = []
    for e in range(int(math.floor(math.log10(lo))) - 1, int(math.ceil(math.log10(hi))) + 1):
        for m in mant:
            L = m * 10.0 ** e * shift
            if lo <= L <= hi: out.append(L)
    return out
def run(mant, shift):
    rows = []
    for s, a in K.items():
        c = a["c"].astype(np.float64); qv = a["qv"].astype(np.float64); n = len(c)
        if n < 2000 or c.min() <= 0: continue
        v24 = np.convolve(qv, np.ones(96), "full")[:n]
        mx = np.full(n, np.inf); mn = np.full(n, -np.inf)
        mx[96:] = sw(c[:-1], 96).max(1)[:n - 96]; mn[96:] = sw(c[:-1], 96).min(1)[:n - 96]   # максимум/минимум закрытий за прошлые сутки
        for L in levels(c.min(), c.max(), mant, shift):
            up = np.flatnonzero((c[:-1] < L) & (c[1:] >= L)) + 1; dn = np.flatnonzero((c[:-1] >= L) & (c[1:] < L)) + 1
            for j in up:
                if 100 <= j < n - 97 and mx[j] < L and v24[j] >= 3e6:
                    rows.append((s, a["t"][j] + 900, 1, c[j] / L - 1, c[j + 4] / c[j] - 1, c[j + 16] / c[j] - 1, c[j + 96] / c[j] - 1))
            for j in dn:
                if 100 <= j < n - 97 and mn[j] >= L and v24[j] >= 3e6:
                    rows.append((s, a["t"][j] + 900, -1, c[j] / L - 1, c[j + 4] / c[j] - 1, c[j + 16] / c[j] - 1, c[j + 96] / c[j] - 1))
    return pd.DataFrame(rows, columns=["s", "t", "dir", "over", "f1", "f4", "f24"])
res = {}
for name, mant in (("1-2-5", (1, 2, 5)), ("1…9", tuple(range(1, 10)))):
    for kind, shift in (("круглые", 1.0), ("фальшивые", 1.0378)):
        D = run(mant, shift); D["year"] = np.where(D.t < CUT, 1, 2); res[(name, kind)] = D
        for d, lab in ((1, "пробой вверх"), (-1, "пробой вниз")):
            x = D[D.dir == d]
            y = " | ".join(f"{yr}-й год: 1ч {g.f1.mean() * 100:+.3f} 4ч {g.f4.mean() * 100:+.3f} 24ч {g.f24.mean() * 100:+.3f} ({len(g)})" for yr, g in x.groupby("year"))
            print(f"{name:5s} {kind:9s} {lab:12s} {len(x):6d} | {y}", flush=True)
pickle.dump(res, open("s3/round.pkl", "wb"))
