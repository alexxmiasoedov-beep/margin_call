"""Шорт после объявлений Binance (делистинг спота, делистинг фьючерса, Monitoring Tag): сетка — задержка входа 15/60 мин,
срок 1/3/7/14 сут, стоп +15/25/40%, защита от сквиза (фандинг < −0,1%/8 ч — не входить) — выбор по 1-й половине,
проверка на 2-й; затем журнал (одна открытая сделка на монету) с хеджем BTC."""
import sys, os, re, datetime, itertools
sys.path.insert(0, os.getcwd())
from s12.common import *
import pandas as pd
src = open("s12/events_ann.py").read()
exec(src[src.index("ev = []"):src.index("rows = []")])
def trade(s, ts, delay_m, hold, stop):
    a = K[s]; te = ((ts + delay_m * 60) // 900 + 1) * 900
    if te >= a["t"][-1] - 86400: return None
    e, je = px(a, te); tx = te + hold * 86400; x, jx = px(a, tx)
    seg = a["h"][je:jx].astype(float) / e - 1 if jx > je else np.array([0.0])
    hit = np.flatnonzero(seg >= stop)
    sp = (-stop - 0.005 if len(hit) else -(x / e - 1)) + fsum(s, te, tx) - 0.001
    be, _ = px(btc, te); bx, _ = px(btc, tx)
    return te, sp, sp + bx / be - 1 - 0.001, fnow(s, te)
E2 = []
for kind_, c, ts in ev:
    s = next((p + c for p in ("", "1000", "10000", "100000", "1000000") if p + c in K), None)
    if s and s not in TF: E2.append((kind_, s, ts))
res = []
for delay, hold, stop, guard in itertools.product((15, 60), (1, 3, 7, 14), (0.15, 0.25, 0.4), (False, True)):
    out = []
    for kind_, s, ts in E2:
        r = trade(s, ts, delay, hold, stop)
        if r is None or (guard and r[3] is not None and r[3] < -0.001): continue
        out.append((kind_, s, ts) + r)
    o = pd.DataFrame(out, columns=["kind", "s", "ts", "te", "sp", "h", "f8"]); hh = o.ts < CUT
    res.append(dict(delay=delay, hold=hold, stop=stop, guard=guard, n=len(o), m=o.sp.mean(), m1=o[hh].sp.mean(), m2=o[~hh].sp.mean(),
                    t1=o[hh].sp.mean() / o[hh].sp.std() * np.sqrt(hh.sum()), w=(o.sp > 0).mean(), mh=o.h.mean(), med=o.sp.median()))
R = pd.DataFrame(res)
print(f"вариантов {len(R)}; на 2-й половине в плюсе {(R.m2 > 0).mean():.0%}; медиана 2-й {R.m2.median()*100:+.2f}%; корреляция рангов 1-я↔2-я {R.m1.rank().corr(R.m2.rank()):.2f}")
for _, r in R.sort_values("t1", ascending=False).head(5).iterrows():
    print(f"   задержка {r.delay:.0f} мин, {r.hold:.0f} сут, стоп +{r.stop*100:.0f}%, защита {r.guard}: 1-я {r.m1*100:+.2f}% (t {r.t1:.1f}) → 2-я {r.m2*100:+.2f}%; "
          f"всего n {r.n:.0f} {r.m*100:+.2f}% (медиана {r.med*100:+.2f}, в плюсе {r.w:.0%}, с хеджем {r.mh*100:+.2f})")
print("\nсреднее по сетке (всего / 2-я половина) по параметру:")
for c in ("delay", "hold", "stop", "guard"):
    print(f"   {c:6s} " + "  ".join(f"{k}: {v.m.mean()*100:+.2f}/{v.m2.mean()*100:+.2f}" for k, v in R.groupby(R[c].astype(str))))
# журнал: задержка 15 мин, 3 сут, стоп +25%, защита — одна открытая сделка на монету
out = []
for kind_, s, ts in sorted(E2, key=lambda x: x[2]):
    r = trade(s, ts, 15, 3, 0.25)
    if r is None or (r[3] is not None and r[3] < -0.001): continue
    out.append((kind_, s, ts) + r)
o = pd.DataFrame(out, columns=["kind", "s", "ts", "te", "sp", "h", "f8"]).sort_values("te")
busy = {}; keep = []
for i, r in o.iterrows():
    if busy.get(r.s, 0) > r.te: continue
    busy[r.s] = r.te + 3 * 86400; keep.append(i)
j = o.loc[keep]; hh = j.ts < CUT
mon = j.groupby(pd.to_datetime(j.te, unit="s").dt.to_period("M")).sp.agg(["sum", "size"])
print(f"\nжурнал (15 мин, 3 сут, стоп +25%, защита, одна сделка на монету): сделок {len(j)} ({len(j)/((j.te.max()-j.te.min())/86400/30.4):.1f} в месяц), "
      f"{j.sp.mean()*100:+.2f}% на сделку (медиана {j.sp.median()*100:+.2f}, в плюсе {(j.sp > 0).mean():.0%}; 1-я {j[hh].sp.mean()*100:+.2f} / 2-я {j[~hh].sp.mean()*100:+.2f}); "
      f"с хеджем {j.h.mean()*100:+.2f}%; месяцев в плюсе {(mon['sum'] > 0).sum()}/{len(mon)}; итог при 1 USDT ×1: {j.sp.sum():+.1f} USDT")
print("   по типам:", "; ".join(f"{k}: n {len(g)} {g.sp.mean()*100:+.2f}%" for k, g in j.groupby("kind")))
print("   худшие:", ", ".join(f"{s} {v*100:+.0f}%" for s, v in j.nsmallest(5, "sp")[["s", "sp"]].values))
