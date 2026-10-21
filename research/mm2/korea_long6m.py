"""Зеркало: лонг после пампа, когда корейцы в нём НЕ участвуют (монеты нет на Upbit/Bithumb или доля Кореи < 5%). 6,5 месяца."""
import pickle, datetime, re, os
import numpy as np
from pump_short6m import K, fund_short
import korea_short6m as ks
MSK = datetime.timezone(datetime.timedelta(hours=3))
def lng(k, j, tp, sl, hold):
    e = k[j, 4]
    for q in range(j + 1, min(j + 1 + hold, len(k))):
        if k[q, 3] <= e * (1 - sl): return -sl, k[q, 0] + 900
        if k[q, 2] >= e * (1 + tp): return tp, k[q, 0] + 900
    q = min(j + hold, len(k) - 1); return k[q, 4] / e - 1, k[q, 0] + 900
G = {}
for s, j, i in ks.EV:
    k = K[s]
    if j + 2 >= len(k) or j < 100: continue
    ka = ks.kr_arrays(s, j); t_in = k[j, 0] + 900
    if ka is None: G.setdefault("нет в Корее", []).append((s, j, t_in)); continue
    sh = ks.share(ka[0], k, j)
    G.setdefault("в Корее, доля < 5%" if sh < 0.05 else ("в Корее, доля 5–20%" if sh < 0.2 else "в Корее, доля ≥ 20%"), []).append((s, j, t_in))
for tp, sl, hold in ((0.10, 0.05, 8), (0.15, 0.07, 24), (0.20, 0.10, 96), (0.30, 0.15, 192)):
    print(f"\n=== ЛОНГ сразу после пампа: тейк {tp:.0%} / стоп {sl:.0%} / {hold // 4} ч (комиссия 0,1%, фандинг — лонг получает отрицательный)")
    for name in ("нет в Корее", "в Корее, доля < 5%", "в Корее, доля 5–20%", "в Корее, доля ≥ 20%"):
        res = []
        for s, j, t_in in G[name]:
            pnl, t_out = lng(K[s], j, tp, sl, hold); res.append((t_in, pnl - 0.001 - fund_short(s, t_in, t_out)))
        a = np.array(res); line = f"{name:22s} {len(a):4d} сд. | итог {a[:, 1].mean():+.2%} | плюс {np.mean(a[:, 1] > 0):.0%} |"
        for mo in range(4, 11):
            t0 = datetime.datetime(2026, mo, 1, tzinfo=MSK).timestamp(); t1 = datetime.datetime(2026, mo + 1, 1, tzinfo=MSK).timestamp()
            b = a[(a[:, 0] >= t0) & (a[:, 0] < t1), 1]; line += f" {mo:02d}: {b.mean():+.1%} ({len(b)})" if len(b) else f" {mo:02d}: —"
        print(line)
