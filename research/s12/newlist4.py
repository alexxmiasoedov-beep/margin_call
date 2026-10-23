"""Правило «новый токен со спотовым листингом Binance + займ в канале → шорт»: фильтр фандинга на входе (< −0,1%/8 ч — не
входить), выход при фандинге ≤ −0,5%/8 ч два раза подряд, кварталы, сетка входа/срока с выбором по 1-й половине."""
import pickle, re, datetime, itertools
import numpy as np, pandas as pd
import sys, os
sys.path.insert(0, os.getcwd())
from s12.common import *
def run(s, a, ent_h, hold_d, stop, fcut, fexit):
    T0 = int(a["t"][0]); te = T0 + ent_h * 3600; e, je = px(a, te)
    f = FU.get(s)
    if f is not None and fcut is not None:
        k = np.searchsorted(f[:, 0], te, "right") - 1
        if k >= 0 and f[k, 2] / f[k, 1] * 8 < fcut: return None              # дорогой шорт — не входим
    tx = te + hold_d * 86400
    if tx > T_END: return None
    if f is not None and fexit is not None:                                  # два начисления подряд ≤ fexit (за 8 ч) — выход
        ff = f[(f[:, 0] > te) & (f[:, 0] <= tx)]; bad = ff[:, 2] / ff[:, 1] * 8 <= fexit
        two = np.flatnonzero(bad[1:] & bad[:-1])
        if len(two): tx = int(ff[two[0] + 1, 0])
    x, jx = px(a, tx); seg = a["h"][je:jx].astype(float) / e - 1 if jx > je else np.array([0.0])
    hit = np.flatnonzero(seg >= stop)
    sp = (-stop - 0.005 if len(hit) else -(x / e - 1)) + fsum(s, te, tx) - 0.001
    be, _ = px(btc, te); bx, _ = px(btc, tx)
    return sp, sp + bx / be - 1 - 0.001
ev = []
for s, a in K.items():
    T0 = int(a["t"][0])
    if T0 < CH0 or s in TF or s.endswith("USDC") or len(a["t"]) < 96 * 4: continue
    sa = spot_ann.get(strip(s)) or spot_ann.get(s)
    if not (sa is not None and abs(sa - T0) <= 10 * 86400): continue
    tt = ch.get(strip(s)); tt = tt if tt is not None else np.array([])
    ev.append((s, a, T0, tt))
print("новых токенов со спотовым листингом Binance в эпоху канала:", len(ev))
res = []
for ent, hold, stop, fcut, fexit in itertools.product((1, 6, 24, 48, 72), (7, 14, 21, 30), (0.6, 1.0), (None, -0.001), (None, -0.005)):
    out = []
    for s, a, T0, tt in ev:
        te = T0 + ent * 3600
        if ((tt >= T0 - 48 * 3600) & (tt < te)).sum() == 0: continue
        r = run(s, a, ent, hold, stop, fcut, fexit)
        if r: out.append((T0, s) + r)
    if not out: continue
    o = pd.DataFrame(out, columns=["T0", "s", "sp", "h"]); hh = o.T0 < CUT
    res.append(dict(ent=ent, hold=hold, stop=stop, fcut=fcut, fexit=fexit, n=len(o), n1=hh.sum(), n2=(~hh).sum(), m=o.sp.mean(), m1=o[hh].sp.mean(),
                    m2=o[~hh].sp.mean(), med=o.sp.median(), w=(o.sp > 0).mean(), mh=o.h.mean(), worst=o.sp.min(),
                    t1=o[hh].sp.mean() / o[hh].sp.std() * np.sqrt(hh.sum()), no5=o.sp.drop(o.sp.nlargest(5).index).mean()))
R = pd.DataFrame(res); R.to_pickle("s12/newlist4_grid.pkl")
print(f"вариантов {len(R)}; на 2-й половине в плюсе {(R.m2 > 0).mean():.0%}; медиана 2-й {R.m2.median()*100:+.1f}%; без 5 лучших в плюсе {(R.no5 > 0).mean():.0%}")
for _, r in R.sort_values("t1", ascending=False).head(6).iterrows():
    print(f"   вход {r.ent:.0f} ч, {r.hold:.0f} сут, стоп +{r.stop*100:.0f}%, фильтр фандинга {r.fcut}, выход по фандингу {r.fexit}: "
          f"1-я {r.m1*100:+.1f}% (n {r.n1:.0f}, t {r.t1:.1f}) → 2-я {r.m2*100:+.1f}% (n {r.n2:.0f}); всего {r.m*100:+.1f}% (медиана {r.med*100:+.1f}, "
          f"в плюсе {r.w:.0%}, без 5 лучших {r.no5*100:+.1f}, худшая {r.worst*100:+.0f}%, с хеджем {r.mh*100:+.1f})")
print("\nвлияние фильтров (среднее по сетке, всего / 2-я половина):")
for c in ("fcut", "fexit", "stop", "ent", "hold"):
    print(f"   {c:6s} " + "  ".join(f"{k}: {v.m.mean()*100:+.1f}/{v.m2.mean()*100:+.1f}" for k, v in R.groupby(R[c].astype(str))))
base = []
for s, a, T0, tt in ev:
    if ((tt >= T0 - 48 * 3600) & (tt < T0 + 24 * 3600)).sum() == 0: continue
    r = run(s, a, 24, 14, 1.0, -0.001, -0.005)
    if r: base.append((T0, s) + r)
o = pd.DataFrame(base, columns=["T0", "s", "sp", "h"])
print("\nбазовое правило (вход 24 ч, 14 сут, стоп +100%, фильтр и выход по фандингу) — по кварталам:",
      " ".join(f"{q}: {v*100:+.0f}% ({n})" for q, v, n in zip(*(lambda g: (g.mean().index, g.mean().values, g.size().values))(o.groupby(pd.to_datetime(o.T0, unit='s').dt.to_period('Q').astype(str)).sp))))
print("сделки:", ", ".join(f"{s} {v*100:+.0f}%" for s, v in o.sort_values('T0')[['s', 'sp']].values))
