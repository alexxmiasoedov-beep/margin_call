"""Шорт на Binance от открытия торгов новой монеты на Upbit (рынок к воне), март 2025 – октябрь 2026."""
import pickle, datetime
import numpy as np
import bv
UTC = datetime.timezone.utc; MSK = datetime.timezone(datetime.timedelta(hours=3))
L = [x for x in pickle.load(open("mm/upbit_listings.pkl", "rb")) + pickle.load(open("mm/upbit_listings_old.pkl", "rb")) if x["quote"] == "KRW"]
ev = {}
for x in sorted(L, key=lambda x: x["t"]):
    if x["base"] in ev and abs(x["t"] - ev[x["base"]][-1]) < 6 * 3600: continue
    ev.setdefault(x["base"], []).append(x["t"])
E = sorted((t, b) for b, ts in ev.items() for t in ts)
mon = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m")
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
POS = pickle.load(open("kaia/positions.pkl", "rb")); PREM = POS["PREM"]
def load(t, b):
    months = sorted({mon(x) for x in range(int(t) - 86400 * 2, int(t) + 86400 * 4, 86400)})
    mm = [m for m in months if m < "2026-10"]; dd = [day(x) for x in range(int(t) - 86400 * 2, int(t) + 86400 * 4, 86400) if mon(x) == "2026-10" and day(x) <= "2026-10-18"]
    k = bv.kfull(b, "klines", "15m", mm, dd)
    fr = []
    for m in mm:
        for p in bv.rows(bv.fetch(f"monthly/fundingRate/{b}USDT/{b}USDT-fundingRate-{m}.zip")):
            try: fr.append((int(p[0]) // 1000, float(p[2])))
            except (ValueError, IndexError): pass
    return k, np.array(sorted(fr)) if fr else None
def short(t0, b, k, fr, delay, hold, sl=0.25):
    tt, h, c = k[:, 0], k[:, 2], k[:, 4]
    i0 = int(np.searchsorted(tt, t0, side="right")) - 1 + delay
    if i0 < 8 or i0 + hold >= len(k) or tt[i0] > t0 + 3600 * 2: return None
    p = c[i0] * 0.999; xt = tt[i0 + hold] + 900; px = None
    for d in range(1, hold + 1):
        if h[i0 + d] >= p * (1 + sl): px, xt = p * (1 + sl) * 1.002, tt[i0 + d] + 900; break
    if px is None: px = c[i0 + hold]
    f = fr[(fr[:, 0] > tt[i0] + 900) & (fr[:, 0] <= xt), 1].sum() if fr is not None and len(fr) else 0.0
    return 1 - px / p + f - 0.001, 1 - px / p, f
rows = []
for t, b in E:
    k, fr = load(t, b)
    if k is None or len(k) < 50: continue
    r = {name: short(t, b, k, fr, d, hld) for name, d, hld in (("48 ч", 0, 192), ("72 ч", 0, 288), ("24 ч", 0, 96), ("через 30 мин, 48 ч", 2, 192))}
    if r["48 ч"] is None: continue
    rows.append(dict(base=b, t=t, **r))
pickle.dump(rows, open("mm/upbit_short_all.pkl", "wb"))
print(f"листингов Upbit к воне с фьючерсом Binance на момент листинга: {len(rows)} (всего листингов к воне в выборке: {len(E)})")
P = [("март–декабрь 2025", "2025-03", "2026-01"), ("январь–июнь 2026", "2026-01", "2026-07"), ("июль–октябрь 2026", "2026-07", "2026-11"), ("всё время", "2025-03", "2026-11")]
for name in ("48 ч", "72 ч", "24 ч", "через 30 мин, 48 ч"):
    print(f"\nШорт от открытия торгов на Upbit, {name}, стоп 25%:")
    for pl, a, bnd in P:
        x = [r[name] for r in rows if a <= mon(r["t"]) < bnd and r[name]]
        if not x: continue
        net = np.array([v[0] for v in x]); pr = np.array([v[1] for v in x]); fu = np.array([v[2] for v in x])
        print(f"  {pl:20s} n={len(net):3d} | итог {net.mean()*100:+5.1f}% на сделку (цена {pr.mean()*100:+5.1f}%, фандинг {fu.mean()*100:+5.1f}%), "
              f"медиана {np.median(net)*100:+5.1f}%, в плюсе {np.mean(net > 0)*100:3.0f}%, стопов {np.mean(pr < -0.24)*100:3.0f}%")
