"""Какие новые листинги падают: признаки первых суток после листинга фьючерса → шорт через сутки (тейк 30 / стоп 30 / 14 дн.),
корзины признаков отдельно на 1-м и 2-м году."""
import pickle, datetime, re
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
syms = set(open("s2/spot_syms.txt").read().split()); TRY = pickle.load(open("s2/fiat_TRY.pkl", "rb"))
D_SPOT = pd.read_pickle("s3/pump_spot.pkl")
UTC = datetime.timezone.utc; A = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); Bd = datetime.datetime(2026, 9, 18, tzinfo=UTC).timestamp()
CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp(); strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
B = K["BTC"]; bt = {int(t): float(c) for t, c in zip(B["t"], B["c"])}
exec(open("s2/newlist.py").read().split("new = [")[0].split("def fund(")[0])
def fund(s, a, b):
    fr = F.get(s)
    if fr is None: return 0.0
    m = (fr[:, 0] > a) & (fr[:, 0] <= b); return float(fr[m, 2].sum())
def short(s, j, tp, sl, hold):
    a = K[s]; e = float(a["c"][j]); n = len(a["t"]); end = min(j + hold, n - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64); lo = a["l"][j + 1:end + 1].astype(np.float64)
    ks = np.flatnonzero(hi >= e * (1 + sl)); kt = np.flatnonzero(lo <= e * (1 - tp))
    q1 = ks[0] if len(ks) else 10**9; q2 = kt[0] if len(kt) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; pnl = -sl
    elif q2 < 10**9: q = j + 1 + q2; pnl = tp
    else: q = end; pnl = 1 - float(a["c"][end]) / e
    return pnl - 0.001 + fund(s, a["t"][j] + 900, a["t"][q] + 900)
rows = []
for s, a in K.items():
    t0 = a["t"][0]
    if not (A <= t0 <= Bd) or len(a["t"]) < 96 * 3: continue
    c = a["c"].astype(np.float64); h = a["h"].astype(np.float64); l = a["l"].astype(np.float64); qv = a["qv"].astype(np.float64); j = 96
    fr = F.get(s); f1 = float(fr[(fr[:, 0] > t0) & (fr[:, 0] <= t0 + 86400), 2].sum()) if fr is not None else 0.0
    name = next((n for n in (s, strip(s)) if f"{n}USDT" in syms), None)
    b0, b1 = bt.get(int(t0 // 900 * 900)), bt.get(int(a["t"][j]))
    rows.append(dict(s=s, t=t0, pnl=short(s, j, 0.3, 0.3, 14 * 96), d1=c[j] / c[0] - 1, run1=h[:j + 1].max() / c[0] - 1, dd1=l[:j + 1].min() / c[0] - 1,
                     from_hi1=c[j] / h[:j + 1].max() - 1, vol1=qv[:j + 1].sum(), late=qv[j - 23:j + 1].sum() / max(qv[:j + 1].sum(), 1), fund1=f1,
                     try_pair=any(f"{n}TRY" in syms for n in (s, strip(s))), spot=name is not None,
                     btc7=(b1 / bt.get(int(a["t"][j]) - 7 * 86400, b1) - 1) if b1 else np.nan, price=c[j]))
D = pd.DataFrame(rows); D["y"] = np.where(D.t < CUT, 1, 2); D.to_pickle("s3/newlist.pkl")
print(f"листингов {len(D)}: шорт через сутки 30/30/14 дн. {D.pnl.mean() * 100:+.2f}% (1-й год {D[D.y == 1].pnl.mean() * 100:+.2f}, 2-й {D[D.y == 2].pnl.mean() * 100:+.2f})")
for k in ("d1", "run1", "dd1", "from_hi1", "vol1", "late", "fund1", "btc7", "price"):
    q = pd.qcut(D[k].rank(method="first"), 4, labels=False); line = f"{k:9s}"
    for b in range(4):
        g = D[q == b]; line += f" | Q{b + 1} ≤{g[k].max():.3g}: {g[g.y == 1].pnl.mean() * 100:+.1f}/{g[g.y == 2].pnl.mean() * 100:+.1f}"
    print(line)
for k in ("spot", "try_pair"):
    print(f"{k:9s} | да: {D[D[k] & (D.y == 1)].pnl.mean() * 100:+.1f}/{D[D[k] & (D.y == 2)].pnl.mean() * 100:+.1f} ({D[k].sum()}) | нет: {D[~D[k] & (D.y == 1)].pnl.mean() * 100:+.1f}/{D[~D[k] & (D.y == 2)].pnl.mean() * 100:+.1f} ({(~D[k]).sum()})")
