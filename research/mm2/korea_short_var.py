"""Варианты корейского шорта на 6,5 месяца: порог доли, момент входа, выходы, премия Кореи, биржа, просадка."""
import pickle, datetime, re, os
import numpy as np
from pump_short6m import K, fund_short, trade
import korea_short6m as ks
MSK = datetime.timezone(datetime.timedelta(hours=3))
def months(a):
    s = ""
    for mo in range(4, 11):
        t0 = datetime.datetime(2026, mo, 1, tzinfo=MSK).timestamp(); t1 = datetime.datetime(2026, mo + 1, 1, tzinfo=MSK).timestamp()
        b = a[(a[:, 0] >= t0) & (a[:, 0] < t1), 1]; s += f" {b.mean():+.1%}" if len(b) else "  —  "
    return s
def evaluate(name, picks, tp=0.15, sl=0.25, hold=192, extra=""):
    res = []
    for s, m in picks:
        k = K[s]; t_in = k[m, 0] + 900; pnl, t_out = trade(k, m, tp, sl, hold); res.append((t_in, pnl - 0.001 + fund_short(s, t_in, t_out)))
    a = np.array(res); a = a[np.argsort(a[:, 0])]
    eq = np.cumsum(a[:, 1]); dd = (eq - np.maximum.accumulate(eq)).min()
    mpos = sum(1 for mo in range(4, 11) if (lambda b: len(b) and b.mean() > 0)(a[(a[:, 0] >= datetime.datetime(2026, mo, 1, tzinfo=MSK).timestamp()) & (a[:, 0] < datetime.datetime(2026, mo + 1, 1, tzinfo=MSK).timestamp()), 1]))
    print(f"{name:46s} {len(a):4d} | {a[:, 1].mean():+.2%} | плюс {np.mean(a[:, 1] > 0):.0%} | мес.+ {mpos}/7 | просадка {dd:+.0%} |{months(a)}")
    return a
P = []
for s, j, i in ks.EV:
    k = K[s]
    if j + 2 >= len(k) or j < 100: continue
    ka = ks.kr_arrays(s, j)
    if ka is None: continue
    vol, close = ka
    pr = close / k[:, 4]; fin = np.isfinite(pr)
    sc = 10 ** np.round(np.log10(np.nanmedian(pr))) if fin.any() else 1; pr = (pr / sc - 1) * 100
    P.append((s, j, vol, pr))
print("пампов монет из Кореи:", len(P), "\nвариант                                         сделок | итог | плюс | мес. в плюсе | просадка (сумма %) | 04 05 06 07 08 09 10")
def first(cond, horizon=96):
    out = []
    for s, j, vol, pr in P:
        k = K[s]
        m = next((m for m in range(j, min(j + horizon, len(k) - 2)) if cond(s, k, m, vol, pr)), None)
        if m is not None: out.append((s, m))
    return out
sh = lambda k, m, vol: ks.share(vol, k, m)
base = first(lambda s, k, m, vol, pr: sh(k, m, vol) >= 0.2)
evaluate("доля ≥ 20% за 24 ч (основной)", base)
evaluate("доля ≥ 20% только в момент пампа", [(s, j) for s, j, vol, pr in P if sh(K[s], j, vol) >= 0.2])
evaluate("доля ≥ 20% за 6 ч после пампа", first(lambda s, k, m, vol, pr: sh(k, m, vol) >= 0.2, 24))
evaluate("доля ≥ 15%", first(lambda s, k, m, vol, pr: sh(k, m, vol) >= 0.15))
evaluate("доля ≥ 25%", first(lambda s, k, m, vol, pr: sh(k, m, vol) >= 0.25))
evaluate("доля ≥ 20% и премия Кореи > 0", first(lambda s, k, m, vol, pr: sh(k, m, vol) >= 0.2 and np.isfinite(pr[m]) and pr[m] > 0))
evaluate("доля ≥ 20% и премия Кореи ≤ 0", first(lambda s, k, m, vol, pr: sh(k, m, vol) >= 0.2 and np.isfinite(pr[m]) and pr[m] <= 0))
evaluate("доля ≥ 20% и премия > 2%", first(lambda s, k, m, vol, pr: sh(k, m, vol) >= 0.2 and np.isfinite(pr[m]) and pr[m] > 2))
for tp, sl, hold in ((0.15, 0.15, 96), (0.20, 0.25, 192), (0.25, 0.30, 288), (0.15, 0.20, 192), (0.10, 0.25, 192)):
    evaluate(f"основной, тейк {tp:.0%} стоп {sl:.0%} {hold // 4} ч", base, tp, sl, hold)
