"""«Флаг» после пампа (лонг на продолжение): памп +15% из покоя; через N ч цена всё ещё держит рост (выше базы на ≥ X%)
и не откатила от максимума больше чем на Y%; вход в закрытии часа N. 6,5 месяца, комиссия 0,1%, фандинг."""
import pickle, datetime
import numpy as np
from pump_short6m import K, fund_short
import korea_short6m as ks
MSK = datetime.timezone(datetime.timedelta(hours=3))
EV = pickle.load(open("mm2/pumps6m.pkl", "rb"))
def lng(k, j, tp, sl, hold):
    e = k[j, 4]
    for q in range(j + 1, min(j + 1 + hold, len(k))):
        if k[q, 3] <= e * (1 - sl): return -sl, k[q, 0] + 900
        if k[q, 2] >= e * (1 + tp): return tp, k[q, 0] + 900
    q = min(j + hold, len(k) - 1); return k[q, 4] / e - 1, k[q, 0] + 900
def run(N, X, Y, tp, sl, hold, kfilter=None):
    res = []
    for s, j, i in EV:
        k = K[s]; m = j + N * 4
        if m + 2 >= len(k) or j < 100: continue
        base = k[i, 4]; hi = k[j:m + 1, 2].max(); c = k[m, 4]
        if c / base - 1 < X or c / hi - 1 < -Y: continue
        if kfilter is not None:
            ka = ks.kr_arrays(s, j)
            if not kfilter(ka, k, m): continue
        pnl, t_out = lng(k, m, tp, sl, hold); t_in = k[m, 0] + 900; res.append((t_in, pnl - 0.001 - fund_short(s, t_in, t_out)))
    if not res: return
    a = np.array(res); line = f"N={N} ч, держит ≥ +{X:.0%} от базы, откат ≤ {Y:.0%}, {tp:.0%}/{sl:.0%}/{hold // 4} ч: {len(a):4d} | {a[:, 1].mean():+.2%} | плюс {np.mean(a[:, 1] > 0):.0%} |"
    for mo in range(4, 11):
        t0 = datetime.datetime(2026, mo, 1, tzinfo=MSK).timestamp(); t1 = datetime.datetime(2026, mo + 1, 1, tzinfo=MSK).timestamp()
        b = a[(a[:, 0] >= t0) & (a[:, 0] < t1), 1]; line += f" {b.mean():+.1%}" if len(b) else " —"
    print(line)
for N in (2, 4, 8):
    for X, Y in ((0.10, 0.08), (0.15, 0.05)):
        for tp, sl, hold in ((0.15, 0.07, 24), (0.25, 0.10, 96)):
            run(N, X, Y, tp, sl, hold)
print("--- то же, только монеты НЕ из Кореи")
for N in (2, 4):
    for X, Y in ((0.10, 0.08), (0.15, 0.05)):
        run(N, X, Y, 0.25, 0.10, 96, lambda ka, k, m: ka is None)
