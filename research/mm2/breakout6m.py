"""Лонг на пробое: закрытие 15-мин свечи выше максимума прошлых D суток при объёме часа ≥ V× среднего за сутки,
рост за сутки ≤ 30%; одна сделка на монету за 24 ч. 6,5 месяца, комиссия 0,1%, фандинг."""
import pickle, datetime
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as sw
from pump_short6m import K, fund_short
MSK = datetime.timezone(datetime.timedelta(hours=3))
def lng(k, j, tp, sl, hold):
    e = k[j, 4]
    for q in range(j + 1, min(j + 1 + hold, len(k))):
        if k[q, 3] <= e * (1 - sl): return -sl, k[q, 0] + 900
        if k[q, 2] >= e * (1 + tp): return tp, k[q, 0] + 900
    q = min(j + hold, len(k) - 1); return k[q, 4] / e - 1, k[q, 0] + 900
def run(D, V, tp, sl, hold):
    res = []
    for s, k in K.items():
        n = len(k); W = 96 * D
        if n < W + 200: continue
        h, c, qv = k[:, 2], k[:, 4], k[:, 6]
        hmax = np.full(n, np.nan); hmax[W:] = sw(h[:-1], W).max(1)[:n - W]          # максимум свечей j−W … j−1
        v1 = np.convolve(qv, np.ones(4), "full")[:n]; v24 = np.convolve(qv, np.ones(96), "full")[:n] / 24
        r24 = np.full(n, np.nan); r24[96:] = c[96:] / c[:-96] - 1
        cand = np.flatnonzero((c > hmax) & (v1 >= V * v24) & (r24 <= 0.3)); last = -10**9
        for j in cand:
            if j - last < 96 or j + 2 >= n: continue
            last = j; pnl, t_out = lng(k, j, tp, sl, hold); t_in = k[j, 0] + 900; res.append((t_in, pnl - 0.001 - fund_short(s, t_in, t_out)))
    a = np.array(res); line = f"пробой {D} сут., объём ≥ {V}×, {tp:.0%}/{sl:.0%}/{hold // 4} ч: {len(a):5d} | {a[:, 1].mean():+.2%} | плюс {np.mean(a[:, 1] > 0):.0%} |"
    for mo in range(4, 11):
        t0 = datetime.datetime(2026, mo, 1, tzinfo=MSK).timestamp(); t1 = datetime.datetime(2026, mo + 1, 1, tzinfo=MSK).timestamp()
        b = a[(a[:, 0] >= t0) & (a[:, 0] < t1), 1]; line += f" {b.mean():+.1%}" if len(b) else " —"
    print(line, flush=True)
for D in (7, 30):
    for V in (3, 6):
        for tp, sl, hold in ((0.10, 0.05, 24), (0.20, 0.10, 96)):
            run(D, V, tp, sl, hold)
