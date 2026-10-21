"""Лонг в начале пампа, пока корейцев нет (монета есть на Upbit/Bithumb, но их доля объёма мала), выход — когда приходят корейцы
(доля ≥ 20%) или по тейку/стопу/времени. 6,5 месяца, комиссия 0,1%, фандинг."""
import pickle, datetime
import numpy as np
from pump_short6m import K, fund_short
import korea_short6m as ks
MSK = datetime.timezone(datetime.timedelta(hours=3))
def run(lo_thr, exit_thr, tp, sl, hold):
    res = []
    for s, j, i in ks.EV:
        k = K[s]
        if j + 2 >= len(k) or j < 100: continue
        ka = ks.kr_arrays(s, j)
        if ka is None or ks.share(ka[0], k, j) >= lo_thr: continue
        e = k[j, 4]; t_in = k[j, 0] + 900; pnl = None
        for q in range(j + 1, min(j + 1 + hold, len(k))):
            if k[q, 3] <= e * (1 - sl): pnl = -sl; break
            if k[q, 2] >= e * (1 + tp): pnl = tp; break
            if exit_thr and ks.share(ka[0], k, q) >= exit_thr: pnl = k[q, 4] / e - 1; break
        if pnl is None: q = min(j + hold, len(k) - 1); pnl = k[q, 4] / e - 1
        res.append((t_in, pnl - 0.001 - fund_short(s, t_in, k[q, 0] + 900)))
    a = np.array(res); line = f"доля < {lo_thr:.0%}, выход при доле ≥ {exit_thr or 0:.0%}, {tp:.0%}/{sl:.0%}/{hold // 4} ч: {len(a):3d} сд. | {a[:, 1].mean():+.2%} | плюс {np.mean(a[:, 1] > 0):.0%} |"
    for mo in range(4, 11):
        t0 = datetime.datetime(2026, mo, 1, tzinfo=MSK).timestamp(); t1 = datetime.datetime(2026, mo + 1, 1, tzinfo=MSK).timestamp()
        b = a[(a[:, 0] >= t0) & (a[:, 0] < t1), 1]; line += f" {b.mean():+.1%}({len(b)})" if len(b) else " —"
    print(line)
for lo in (0.05, 0.10):
    for ex in (None, 0.2, 0.3):
        for tp, sl, hold in ((0.15, 0.07, 24), (0.30, 0.15, 192)):
            run(lo, ex, tp, sl, hold)
