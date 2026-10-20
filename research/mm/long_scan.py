"""Лонг по признакам «монета в игре»: каждые 15 мин по всем монетам. Выход: +15% / −7,5% (что раньше) или через 4 ч; комиссии 0,1%."""
import pickle, datetime, json, re, sys
import numpy as np, pandas as pd
MSK = datetime.timezone(datetime.timedelta(hours=3))
SRC = sys.argv[1] if len(sys.argv) > 1 else "kaia/k15_all.pkl"
T0 = datetime.datetime(*map(int, (sys.argv[2] if len(sys.argv) > 2 else "2026-09-19").split("-")), tzinfo=MSK).timestamp()
T1 = datetime.datetime(*map(int, (sys.argv[3] if len(sys.argv) > 3 else "2026-10-18").split("-")), tzinfo=MSK).timestamp()
OUT = sys.argv[4] if len(sys.argv) > 4 else "mm/long_scan.pkl"
K = pickle.load(open(SRC, "rb"))
rx = re.compile(r'^([A-Z0-9]+)\s+([\d.]+[KMB]?)\s+([\d.]+[KMB]?)\s+([\d.]+)(?:\s+(-?[\d.]+))?\s*$')
CH = {}
for fn in ("posts_old.jsonl", "posts.jsonl", "posts_new.jsonl", "posts_oct.jsonl"):
    for ln in open(fn):
        pid, ts, txt = json.loads(ln); ep = datetime.datetime.fromisoformat(ts).timestamp()
        if ep < T0 - 86400 or ep > T1: continue
        for row in txt.splitlines():
            m = rx.match(row.strip())
            if m: CH.setdefault(m.group(1), []).append(ep)
CH = {s: np.array(sorted(v)) for s, v in CH.items()}
TP, SL, HOLD = 0.15, 0.075, 16
rows = []
for s, k in K.items():
    if len(k) < 96 * 8 + HOLD: continue
    t, o, h, l, c, v, qv, n, tb = (k[:, j] for j in range(9))
    idx = np.arange(96 * 7, len(k) - HOLD); te = t[idx] + 900
    sel = (te >= T0) & (te <= T1)
    if not sel.any(): continue
    idx = idx[sel]; te = te[sel]
    cs = np.cumsum(np.r_[0, qv]); vol24 = (cs[idx + 1] - cs[idx - 95]) / 96; vol7d = (cs[idx - 95] - cs[idx - 96 * 7]) / (96 * 6)
    hh = pd.Series(h).rolling(96).max().values; ll = pd.Series(l).rolling(96).min().values
    range24 = hh[idx] / ll[idx] - 1; ret24 = c[idx] / c[idx - 96] - 1; ret7 = c[idx] / c[idx - 96 * 7] - 1; ret2h = c[idx] / c[idx - 8] - 1
    vol1h = (cs[idx + 1] - cs[idx - 3]) / 4 / (vol24 + 1e-12)
    ch = CH.get(s); inch = np.zeros(len(idx), bool)
    if ch is not None:
        a = np.searchsorted(ch, te - 4 * 3600, side="right"); b = np.searchsorted(ch, te, side="right"); inch = b > a
    # исход лонга: первое касание +15% / −7,5% в следующие 16 свечей; в одной свече — считаем стоп
    p = c[idx]; res = np.full(len(idx), np.nan)
    done = np.zeros(len(idx), bool)
    for d in range(1, HOLD + 1):
        hi = h[idx + d]; lo = l[idx + d]
        stop = ~done & (lo <= p * (1 - SL)); take = ~done & ~stop & (hi >= p * (1 + TP))
        res[stop] = -SL; res[take] = TP; done |= stop | take
    res[~done] = c[idx[~done] + HOLD] / p[~done] - 1
    res -= 0.001
    rows.append(pd.DataFrame(dict(sym=s, te=te, range24=range24, vol24x=vol24 / (vol7d + 1e-12), ret24=ret24, ret7=ret7, ret2h=ret2h,
                                  vol1h=vol1h, inch=inch, pnl=res)))
D = pd.concat(rows, ignore_index=True); D.to_pickle(OUT)
print(f"моментов {len(D)}, монет {D.sym.nunique()} | лонг в любой момент: {D.pnl.mean()*100:+.2f}% на сделку, тейк {np.mean(D.pnl > 0.14)*100:.1f}%, стоп {np.mean(D.pnl < -0.07)*100:.1f}%")
def seg(mask, lab):
    x = D[mask]
    if len(x) == 0: print(f"  {lab}: нет"); return
    days = x.groupby([x.sym, (x.te // 86400)]).pnl.first()          # по монете не чаще раза в сутки — для честного счёта
    print(f"  {lab:60s} моментов {len(x):7d} | {x.pnl.mean()*100:+.2f}% на сделку (раз в сутки по монете: {len(days)} сделок, {days.mean()*100:+.2f}%), "
          f"тейк {np.mean(x.pnl > 0.14)*100:.1f}%, стоп {np.mean(x.pnl < -0.07)*100:.1f}%")
print("По признакам «монета в игре»:")
seg(D.range24 >= 0.15, "размах за сутки ≥ 15%")
seg(D.range24 >= 0.30, "размах за сутки ≥ 30%")
seg(D.vol24x >= 1.5, "объём суток ≥ 1,5× недели")
seg(D.inch, "в маржинальном канале за 4 ч")
seg((D.ret7 > 0.10), "рост за неделю > 10%")
seg((D.range24 >= 0.15) & (D.vol24x >= 1.5), "размах ≥ 15% и объём ≥ 1,5×")
seg((D.range24 >= 0.15) & (D.vol24x >= 1.5) & D.inch, "+ в канале")
seg((D.range24 >= 0.15) & (D.vol24x >= 1.5) & (D.ret24 > 0) & (D.ret2h.abs() <= 0.05), "размах ≥ 15%, объём ≥ 1,5×, сутки в плюсе, 2 ч спокойно")
seg((D.range24 >= 0.15) & (D.vol24x >= 1.5) & (D.ret24 > 0) & (D.ret2h.abs() <= 0.05) & (D.vol1h >= 1.5), "  + объём последнего часа ≥ 1,5× суточного")
