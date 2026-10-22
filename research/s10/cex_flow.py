"""Ончейн-приток токена на кошельки Binance (DefiLlama) → цена фьючерса в следующие дни. Снимок дня d (00:00 UTC) известен
к ~01:00; вход — открытие 15-мин свечи 02:00 UTC дня d; приток за день d−1 = Q(d) − Q(d−1). Исходы — 24/72 ч и тейк/стоп
за 48 ч (шорт и лонг), комиссия 0,1%. Шумные токены (> 3% дней со скачком баланса > 50%) отброшены."""
import pickle, re, datetime
import numpy as np, pandas as pd
Q = pd.read_pickle("s10/cex_qty.pkl").iloc[:-1]; U = pd.read_pickle("s10/cex_usd.pkl").iloc[:-1]
K = pickle.load(open("s2/k2y.pkl", "rb"))
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
fut = {}
for s in K:
    fut.setdefault(strip(s), s)
UTC = datetime.timezone.utc
def path_out(s, t0):
    a = K[s]; t = a["t"]; j = int(np.searchsorted(t, t0))
    if j >= len(t) - 290 or t[j] != t0: return None
    e = float(a["o"][j]); o = {"e": e}
    for hh, n in (("r24", 96), ("r72", 288)): o[hh] = float(a["c"][j + n - 1]) / e - 1
    hi = a["h"][j:j + 192].astype(float) / e - 1; lo = a["l"][j:j + 192].astype(float) / e - 1
    for side in ("S", "L"):
        for tp, sl in ((10, 20), (7, 15), (5, 10)):
            g = np.flatnonzero(lo <= -tp / 100 if side == "S" else hi >= tp / 100); b = np.flatnonzero(hi >= sl / 100 if side == "S" else lo <= -sl / 100)
            g = g[0] if len(g) else 10**9; b = b[0] if len(b) else 10**9
            if b <= g and b < 10**9: px = -sl / 100
            elif g < 10**9: px = tp / 100
            else: px = (float(a["c"][j + 191]) / e - 1) * (-1 if side == "S" else 1)
            o[f"{side}_{tp}_{sl}"] = px - 0.001
    o["vol30"] = float(a["qv"][max(0, j - 2880):j].astype(float).sum()) / 30   # средний суточный объём фьючерса за 30 дней, $
    return o
rows = []
for tok in Q.columns:
    s = fut.get(tok)
    if s is None: continue
    q = Q[tok].loc["2024-09-01":]; u = U[tok].loc["2024-09-01":]
    q = q[q > 0].dropna()
    if len(q) < 60: continue
    jumps = (q.pct_change().abs() > 0.5).mean()
    if jumps > 0.03: continue
    px = (u / Q[tok]).reindex(q.index)
    for d in q.index[1:]:
        prev = q.index[q.index.get_loc(d) - 1]
        if (d - prev).days != 1: continue
        dq = q[d] - q[prev]; usd = dq * px.get(d, np.nan)
        t0 = int((d + pd.Timedelta(hours=2)).timestamp())
        o = path_out(s, t0)
        if o is None or not np.isfinite(usd): continue
        rows.append(dict(tok=tok, s=s, d=d, rel=dq / q[prev], usd=usd, bal=q[prev] * px.get(d, np.nan), **o))
D = pd.DataFrame(rows); D["vrel"] = D.usd / D.vol30.clip(lower=1)
D["m"] = D.d.dt.strftime("%y%m"); D.to_pickle("s10/cex_events.pkl")
print("наблюдений (токен × день):", len(D), "| токенов:", D.tok.nunique(), "|", D.d.min().date(), "→", D.d.max().date())
print("рынок в среднем: r24 %+.2f%%, r72 %+.2f%%" % (D.r24.mean() * 100, D.r72.mean() * 100))
def show(nm, g):
    if len(g) < 30: print(f"{nm:44s} n={len(g)}"); return
    h1, h2 = g[g.d < "2026-04-01"], g[g.d >= "2026-04-01"]
    print(f"{nm:44s} n={len(g):5d} r24 {g.r24.mean()*100:+.2f}% r72 {g.r72.mean()*100:+.2f}% | S_7_15 {g.S_7_15.mean()*100:+.2f}% WR {(g.S_7_15 > 0).mean():.0%} "
          f"| L_7_15 {g.L_7_15.mean()*100:+.2f}% | 1-я/2-я S {h1.S_7_15.mean()*100:+.2f}/{h2.S_7_15.mean()*100:+.2f} (n {len(h1)}/{len(h2)})")
show("все", D)
for lo, hi in ((0.02, 0.05), (0.05, 0.10), (0.10, 0.25), (0.25, 9)):
    show(f"приток +{lo:.0%}…+{hi:.0%} баланса", D[(D.rel >= lo) & (D.rel < hi) & (D.usd >= 2e5)])
for lo, hi in ((0.02, 0.05), (0.05, 0.10), (0.10, 0.25), (0.25, 9)):
    show(f"отток −{lo:.0%}…−{hi:.0%} баланса", D[(D.rel <= -lo) & (D.rel > -hi) & (D.usd <= -2e5)])
for lo in (0.05, 0.2, 0.5, 1.0):
    show(f"приток ≥ {lo:.0%} суточного объёма фьючерса", D[D.vrel >= lo])
    show(f"отток ≥ {lo:.0%} суточного объёма фьючерса", D[D.vrel <= -lo])
