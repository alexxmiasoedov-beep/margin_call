"""Бэктест корейского шорта за два года (19.10.2024–18.10.2026), без заглядывания вперёд.
Памп: +15% за ≤ 2 ч из покоя (причинно, load2y.py). Правило: в закрытии свечи пампа доля Upbit + Bithumb в объёме за час ≥ 20%
→ шорт в закрытии, тейк 10% / стоп 25% / 48 ч (стоп первым в общей свече), комиссия 0,1%, фандинг — фактический из архива Binance
(октябрь 2026 — оценка по индексу премии). Деньги — как в боте: маржа 1 USDT × 10."""
import pickle, datetime, re, os, glob, sys
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import bv
UTC = datetime.timezone.utc; MSK = datetime.timezone(datetime.timedelta(hours=3))
D = pickle.load(open("mm2/pumps2y.pkl", "rb")); EV = D["EV"]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
# ---- курс KRW-USDT
FX = {}
for ex in ("upbit", "bithumb"):
    a = np.vstack([np.load(f) for f in glob.glob(f"mm2/korea2y/{ex}_USDT_*.npy") if os.path.getsize(f) > 200])
    a = a[np.argsort(a[:, 0])]; _, u = np.unique(a[:, 0], return_index=True); FX[ex] = a[u]
# ---- фандинг: архив по месяцам (+ оценка по премии для октября 2026)
MONTHS = sorted({datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m") for e in EV for t in (e["t_in"], e["t_in"] + 3 * 86400)})
def fr(sym):
    out = []
    for m in MONTHS:
        if m >= "2026-10": continue
        for p in bv.rows(bv.fetch(f"monthly/fundingRate/{sym}USDT/{sym}USDT-fundingRate-{m}.zip")):
            try: out.append((int(p[0]) // 1000, float(p[1]), float(p[2])))
            except (ValueError, IndexError): pass
    return sym, np.array(sorted(out)) if out else None
with ThreadPoolExecutor(16) as ex: FUND = dict(ex.map(fr, sorted({e["s"] for e in EV})))
PREM = pickle.load(open("kaia/positions.pkl", "rb"))["PREM"]
OCT = [f"2026-10-{d:02d}" for d in range(1, 21)]
def prem_oct(sym):
    if sym in PREM and PREM[sym][-1, 0] >= datetime.datetime(2026, 10, 18, tzinfo=UTC).timestamp(): return sym, PREM[sym]
    try: return sym, bv.klines(sym, "premiumIndexKlines", "15m", (), OCT)
    except Exception: return sym, None
late = sorted({e["s"] for e in EV if e["t_in"] + 3 * 86400 >= datetime.datetime(2026, 9, 28, tzinfo=UTC).timestamp()})
with ThreadPoolExecutor(16) as ex: POCT = dict(ex.map(prem_oct, late))
def fund_short(s, t_in, t_out):
    fu = FUND.get(s); tot = 0.0; last = 0; iv = 8
    if fu is not None and len(fu):
        m = (fu[:, 0] > t_in) & (fu[:, 0] <= t_out); tot += fu[m, 2].sum(); last = fu[-1, 0]; iv = int(fu[-1, 1]) or 8
    p = POCT.get(s)
    if t_out > max(last, datetime.datetime(2026, 10, 1, tzinfo=UTC).timestamp() - 1) and p is not None:
        t = (int(max(t_in, last, datetime.datetime(2026, 10, 1, tzinfo=UTC).timestamp() - 1)) // (iv * 3600) + 1) * iv * 3600
        while t <= t_out:
            m = (p[:, 0] >= t - iv * 3600) & (p[:, 0] < t)
            if m.any():
                pr = p[m, 4].mean(); tot += float(np.clip((pr + np.clip(0.0001 - pr, -0.0005, 0.0005)) * iv / 8, -0.02, 0.02))
            t += iv * 3600
    return tot
# ---- Корея вокруг пампа, выровненная по окну свечей
def kr(e):
    w = e["w"]; n = len(w); vol = np.zeros(n); close = np.full(n, np.nan); listed = []
    for ex in ("upbit", "bithumb"):
        fn = f"mm2/korea2y/{ex}_{strip(e['s'])}_{int(e['t_in'] + 26 * 3600)}.npy"
        if not os.path.exists(fn): continue
        a = np.load(fn)
        if not len(a): continue
        listed.append(ex)
        idx = np.searchsorted(w[:, 0], a[:, 0]); ok = idx < n; ok[ok] &= w[idx[ok], 0] == a[ok, 0]
        fxv = np.interp(a[:, 0], FX[ex][:, 0], FX[ex][:, 4]); np.add.at(vol, idx[ok], a[ok, 5] / fxv[ok])
        sel = idx[ok]; fill = np.isnan(close[sel]); close[sel[fill]] = (a[ok, 4] / fxv[ok])[fill]
    return (vol, close, listed) if listed else None
def share(vol, w, m):
    v = vol[m - 3:m + 1].sum(); f = w[m - 3:m + 1, 4].sum(); return v / (v + f + 1e-9)
def short(w, j, tp, sl, hold):
    e = w[j, 3]
    for q in range(j + 1, min(j + 1 + hold, len(w))):
        if w[q, 1] >= e * (1 + sl): return -sl, w[q, 0] + 900, "стоп"
        if w[q, 2] <= e * (1 - tp): return tp, w[q, 0] + 900, "тейк"
    q = min(j + hold, len(w) - 1); return 1 - w[q, 3] / e, w[q, 0] + 900, "время"
R = []
for e in EV:
    k = kr(e); w = e["w"]; j = e["j"]
    r = dict(s=e["s"], t_in=e["t_in"], korea=k is not None, ex="+".join(k[2]) if k else "", share=share(k[0], w, j) if k else np.nan)
    if k is not None:
        m = next((m for m in range(j, min(j + 96, len(w) - 2)) if share(k[0], w, m) >= 0.2), None); r["m24"] = m
    for tp, sl in ((0.10, 0.25), (0.15, 0.25)):
        pnl, t_out, how = short(w, j, tp, sl, 192); fd = fund_short(e["s"], e["t_in"], t_out)
        r[f"pnl_{int(tp * 100)}"] = pnl - 0.001 + fd; r[f"fund_{int(tp * 100)}"] = fd; r[f"out_{int(tp * 100)}"] = t_out; r[f"how_{int(tp * 100)}"] = how
    if k is not None and r["m24"] is not None:
        m = r["m24"]; pnl, t_out, how = short(w, m, 0.10, 0.25, 192); t_m = w[m, 0] + 900
        r["pnl24_10"] = pnl - 0.001 + fund_short(e["s"], t_m, t_out)
    R.append(r)
pickle.dump(R, open("mm2/bt2y.pkl", "wb"))
print("пампов", len(R), "| монета в Корее в момент пампа:", sum(r["korea"] for r in R), "| из них доля ≥ 20%:", sum(r["korea"] and r["share"] >= 0.2 for r in R))
