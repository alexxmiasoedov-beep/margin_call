"""Шорт на Binance в момент открытия торгов новой монеты на Upbit: задержки входа, выходы, фандинг, устойчивость по половинам."""
import pickle, datetime
import numpy as np
import bv
UTC = datetime.timezone.utc
R = pickle.load(open("mm/upbit_rows.pkl", "rb")); K = pickle.load(open("kaia/k15_6m.pkl", "rb"))
POS = pickle.load(open("kaia/positions.pkl", "rb")); FUND, PREM = POS["FUND"], POS["PREM"]
MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
for r in R:
    s = r["base"]
    if s not in FUND:
        rows = []
        for m in MONTHS:
            for p in bv.rows(bv.fetch(f"monthly/fundingRate/{s}USDT/{s}USDT-fundingRate-{m}.zip")):
                try: rows.append((int(p[0]) // 1000, int(float(p[1])), float(p[2])))
                except (ValueError, IndexError): pass
        if rows: FUND[s] = np.array(sorted(rows))
    if s not in PREM:
        PREM[s] = bv.klines(s, "premiumIndexKlines", "15m", ("2026-09",), [f"2026-10-{d:02d}" for d in range(1, 19)])
src = open("kaia/posfeat.py").read(); exec(src[src.index("OCT1 ="):src.index("def feats(")])
def funding(sym, a, b):
    f = FUND.get(sym); out = 0.0
    if f is not None and len(f): out += sum(x for t, iv, x in f if a < t <= b)
    if b > OCT1 and PREM.get(sym) is not None:
        fe = fund_oct(sym); last = f[-1, 0] if f is not None and len(f) else 0
        if fe is not None: out += sum(x for t, iv, x in fe if a < t <= b and t > last)
    return out
def short(r, delay, hold, tp=None, sl=None):
    k = K[r["base"]]; t, h, l, c = k[:, 0], k[:, 2], k[:, 3], k[:, 4]
    i0 = int(np.searchsorted(t, r["t"], side="right")) - 1 + delay
    if i0 + hold >= len(k): return None
    p = c[i0] * 0.999; xt = t[i0 + hold] + 900; px = None
    for d in range(1, hold + 1):
        if sl and h[i0 + d] >= p * (1 + sl): px, xt = p * (1 + sl) * 1.002, t[i0 + d] + 900; break
        if tp and l[i0 + d] <= p * (1 - tp): px, xt = p * (1 - tp), t[i0 + d] + 900; break
    if px is None: px = c[i0 + hold]
    pr = 1 - px / p
    return pr + funding(r["base"], t[i0] + 900, xt) - 0.001, pr
G = {"все листинги": lambda r: True, "есть рынок к воне (KRW)": lambda r: "KRW" in r["markets"], "реакция до открытия ≥ +5%": lambda r: r["imp"] >= 0.05,
     "KRW и реакция ≥ +5%": lambda r: "KRW" in r["markets"] and r["imp"] >= 0.05}
MID = datetime.datetime(2026, 7, 15, tzinfo=UTC).timestamp()
V = [("с открытия, 48 ч, без стопа", 0, 192, None, None), ("с открытия, 48 ч, стоп 25%", 0, 192, None, 0.25),
     ("с открытия, тейк 15% / стоп 25%, 48 ч", 0, 192, 0.15, 0.25), ("с открытия, 24 ч, стоп 25%", 0, 96, None, 0.25),
     ("через 30 мин, 48 ч, стоп 25%", 2, 192, None, 0.25), ("через 1 ч, 48 ч, стоп 25%", 4, 192, None, 0.25),
     ("с открытия, 72 ч, стоп 25%", 0, 288, None, 0.25)]
for gname, gf in G.items():
    ev = [r for r in R if gf(r)]
    print(f"\n{gname}: {len(ev)} событий (до 15.07: {sum(r['t'] < MID for r in ev)}, после: {sum(r['t'] >= MID for r in ev)})")
    for name, delay, hold, tp, sl in V:
        x = [(r, short(r, delay, hold, tp, sl)) for r in ev]; x = [(r, v) for r, v in x if v]
        net = np.array([v[0] for _, v in x]); pr = np.array([v[1] for _, v in x])
        a = np.array([v[0] for r, v in x if r["t"] < MID]); b = np.array([v[0] for r, v in x if r["t"] >= MID])
        print(f"  {name:38s} n={len(net):2d} | итог {net.mean()*100:+5.1f}% (цена {pr.mean()*100:+5.1f}%, фандинг {(net - pr + 0.001).mean()*100:+5.1f}%), "
              f"медиана {np.median(net)*100:+5.1f}%, в плюсе {np.mean(net > 0)*100:3.0f}% | 1-я половина {a.mean()*100 if len(a) else 0:+5.1f}% (n={len(a)}), "
              f"2-я {b.mean()*100 if len(b) else 0:+5.1f}% (n={len(b)})")
