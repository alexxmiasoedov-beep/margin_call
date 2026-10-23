"""Объявления Binance как события (Китай №4, СНГ №5): спотовый делистинг, делистинг фьючерса, Monitoring Tag.
Шорт фьючерса с первой 15-мин свечи после объявления; выход через 1/3/7 сут или до расчёта (делистинг фьючерса);
стоп +25%; фандинг и комиссия; защита от сквиза: не входить при фандинге < −0,1%/8 ч."""
import sys, os, re, datetime
sys.path.insert(0, os.getcwd())
from s12.common import *
import pandas as pd
ev = []
for a in A.values():
    if not a["ts"] or a["ts"] < 1727740800000: continue
    t, ts = a["title"], a["ts"] // 1000
    if re.search(r"Monitoring Tag", t):
        m = re.search(r"Include (.+?) on \d", t) or re.search(r"Include (.+)$", t)
        if m: ev += [("monitoring", c.strip(), ts) for c in re.split(r",|&| and ", m.group(1)) if c.strip()]
    elif re.search(r"^Binance Will Delist", t):
        m = re.search(r"Delist (.+?) on \d", t)
        if m: ev += [("spot delist", c.strip(), ts) for c in re.split(r",|&| and ", m.group(1)) if c.strip()]
    elif re.search(r"Futures Will Delist", t):
        ev += [("perp delist", c, ts) for c in re.findall(r"\b([A-Z0-9]{2,20})USDT\b", t)]
print("событий:", pd.Series([e[0] for e in ev]).value_counts().to_dict())
rows = []
for kind_, c, ts in ev:
    s = next((p + c for p in ("", "1000", "10000", "100000", "1000000") if p + c in K), None)
    if s is None: continue
    a = K[s]; te = (ts // 900 + 1) * 900
    if te >= a["t"][-1] - 86400: continue
    e, je = px(a, te)
    f8 = fnow(s, te)
    for hold in (1, 3, 7):
        tx = te + hold * 86400
        x, jx = px(a, tx); seg = a["h"][je:jx].astype(float) / e - 1 if jx > je else np.array([0.0])
        hit = np.flatnonzero(seg >= 0.25)
        sp = (-0.25 - 0.005 if len(hit) else -(x / e - 1)) + fsum(s, te, tx) - 0.001
        rows.append(dict(kind=kind_, s=s, ts=ts, hold=hold, sp=sp, f8=f8, stop=len(hit) > 0))
E = pd.DataFrame(rows)
for (k, h), g in E.groupby(["kind", "hold"]):
    hh = g.ts < CUT; ok = g[~(g.f8 < -0.001)]
    print(f"   {k:12s} {h} сут: n {len(g):3d} шорт {g.sp.mean()*100:+6.2f}% (медиана {g.sp.median()*100:+6.2f}, в плюсе {(g.sp > 0).mean():.0%}, "
          f"1-я {g[hh].sp.mean()*100:+6.2f} / 2-я {g[~hh].sp.mean()*100:+6.2f}, стопов {g.stop.mean():.0%}) | с защитой от сквиза: n {len(ok)} {ok.sp.mean()*100:+6.2f}%")
