"""Годовщина листинга: у новых токенов стандартный «клифф» разлока команды и фондов через 6 и 12 месяцев после выпуска.
Средняя доходность к рынку (равновзвешенный индекс всех фьючерсов) по дням вокруг 180-го и 365-го дня после первой свечи на Binance."""
import pickle, datetime
import numpy as np, pandas as pd
T = np.load("s4/T.npy"); C = np.load("s4/G_c.npy"); syms = pickle.load(open("s4/syms.pkl", "rb"))
n, m = C.shape; first = np.argmax(~np.isnan(C), axis=0)
UTC = datetime.timezone.utc; t_start = datetime.datetime(2024, 10, 3, tzinfo=UTC).timestamp()
# дневные закрытия в 00:00 UTC
day = np.flatnonzero(T % 86400 == 85500)  # свечи 23:45, закрываются в 00:00
Cd = C[day]; Td = T[day] + 900
R = Cd[1:] / Cd[:-1] - 1; R[np.abs(R) > 3] = np.nan
mkt = np.nanmean(np.where(np.isnan(R), np.nan, R), axis=1)
X = R - mkt[:, None]                     # доходность к рынку за день
fd = np.array([np.searchsorted(Td, T[f]) for f in first])   # индекс первого дневного закрытия после листинга
new = [k for k in range(m) if T[first[k]] >= t_start]
print("новых листингов", len(new))
for anchor, lo, hi in ((180, -60, 60), (365, -60, 60)):
    acc = {}
    for k in new:
        a = fd[k] + anchor
        for d in range(lo, hi):
            i = a + d - 1
            if 0 <= i < len(X) and not np.isnan(X[i, k]): acc.setdefault(d, []).append(X[i, k])
    print(f"\nдень {anchor}: монет с данными на дне 0 — {len(acc.get(0, []))}")
    cum = 0; line = []
    for d in range(lo, hi):
        v = acc.get(d, []); mu = np.mean(v) if v else 0; cum += mu
        if d % 5 == 4: line.append(f"{d + 1:+d}: {cum * 100:+.1f}% ({len(v)})")
    print("  накопленная доходность к рынку от дня −60:", " | ".join(line))
