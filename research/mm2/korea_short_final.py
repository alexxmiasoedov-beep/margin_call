"""Итоговое правило корейского шорта (вход в момент пампа), 6,5 месяца: по месяцам, просадка, одновременные позиции.
Деньги — как в боте: маржа 1 USDT × плечо 10 = 10 USDT на сделку."""
import pickle, datetime
import numpy as np
from pump_short6m import K, fund_short, trade
import korea_short6m as ks
MSK = datetime.timezone(datetime.timedelta(hours=3))
T = []
for s, j, i in ks.EV:
    k = K[s]
    if j + 2 >= len(k) or j < 100: continue
    ka = ks.kr_arrays(s, j)
    if ka is None or ks.share(ka[0], k, j) < 0.2: continue
    for tp, sl in ((0.15, 0.25), (0.10, 0.25)):
        t_in = k[j, 0] + 900; pnl, t_out = trade(k, j, tp, sl, 192); fd = fund_short(s, t_in, t_out)
        T.append(dict(s=s, tp=tp, t_in=t_in, t_out=t_out, pnl=pnl - 0.001 + fd, fund=fd, share=ks.share(ka[0], k, j)))
for tp in (0.15, 0.10):
    a = sorted([x for x in T if x["tp"] == tp], key=lambda x: x["t_in"]); p = np.array([x["pnl"] for x in a]) * 10
    eq = np.cumsum(p); dd = (eq - np.maximum.accumulate(eq)).min()
    ev = sorted([(x["t_in"], 1) for x in a] + [(x["t_out"], -1) for x in a]); cur = mx = 0
    for _, d in ev: cur += d; mx = max(mx, cur)
    print(f"\nтейк {tp:.0%} / стоп 25% / 48 ч: {len(a)} сделок у {len({x['s'] for x in a})} монет, в среднем {p.mean():+.3f} USDT на сделку "
          f"({p.mean() / 10:+.2%}), всего {p.sum():+.1f} USDT, худшая просадка {dd:+.1f} USDT, одновременно до {mx} позиций, фандинг {np.mean([x['fund'] for x in a]):+.2%}")
    for mo in range(4, 11):
        t0 = datetime.datetime(2026, mo, 1, tzinfo=MSK).timestamp(); t1 = datetime.datetime(2026, mo + 1, 1, tzinfo=MSK).timestamp()
        b = np.array([x["pnl"] * 10 for x in a if t0 <= x["t_in"] < t1])
        print(f"  {mo:02d}.2026: {len(b):3d} сделок, {b.sum():+6.1f} USDT, в плюсе {np.mean(b > 0):.0%}")
pickle.dump(T, open("mm2/korea_short_final.pkl", "wb"))
