"""Доля площадки (cb — Coinbase, ku — KuCoin, bg — Bitget, okx — OKX, bvv — Bitvavo; по умолчанию Coinbase) в объёме за час на момент пампа и её «обычная» доля (медиана часовых долей
за сутки до этого); премия цены площадки к фьючерсу Binance. Исходы: шорт 10/25/48 ч (как в корейском правиле) и лонг."""
import json, pickle, re, os, sys, datetime
import numpy as np, pandas as pd
V = sys.argv[1] if len(sys.argv) > 1 else "cb"
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb")); P = pd.read_pickle("s2/pump_TRY.pkl")
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
def load(c, t):
    fn = f"s8/{V}/{c}_{int(t)}.json" if V == "bvv" else f"s5/{V}/{c}_{int(t)}.json"
    if not os.path.exists(fn): return None
    j = json.load(open(fn))
    if not isinstance(j, list): return None
    if V == "cb":   # [time, low, high, open, close, volume]
        return {int(x[0]): (float(x[5]) * float(x[4]), float(x[4])) for x in j}
    if V == "ku":   # [time, open, close, high, low, volume, turnover]
        return {int(x[0]): (float(x[6]), float(x[2])) for x in j}
    if V == "bg":   # [ts мс, o, h, l, c, baseVol, usdtVol, quoteVol]
        return {int(x[0]) // 1000: (float(x[6]), float(x[4])) for x in j}
    if V == "bvv":  # Bitvavo: [ts мс, o, h, l, c, объём в монетах], цены в евро → доллары по EUR/USDT
        fx = np.load("s8/eurusd.npy"); r = lambda ts: np.interp(ts, fx[:, 0], fx[:, 1])
        return {int(x[0]) // 1000: (float(x[5]) * float(x[4]) * r(int(x[0]) // 1000), float(x[4]) * r(int(x[0]) // 1000)) for x in j}
    if V == "okx":  # [ts мс, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
        return {int(x[0]) // 1000: (float(x[7]), float(x[4])) for x in j}
    return None
def fund(s, a, b):
    fr = F.get(s)
    if fr is None: return 0.0
    ft = fr[:, 0].astype(np.float64); m = (ft > a) & (ft <= b); return float(fr[m, 2].astype(np.float64).sum())
def trade(s, j, side, tp, sl, hold):
    a = K[s]; t = a["t"]; e = float(a["c"][j]); end = min(j + hold, len(t) - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64); lo = a["l"][j + 1:end + 1].astype(np.float64)
    if side > 0: ks = np.flatnonzero(lo <= e * (1 - sl)); kt = np.flatnonzero(hi >= e * (1 + tp))
    else: ks = np.flatnonzero(hi >= e * (1 + sl)); kt = np.flatnonzero(lo <= e * (1 - tp))
    q1 = ks[0] if len(ks) else 10**9; q2 = kt[0] if len(kt) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; pnl = -sl
    elif q2 < 10**9: q = j + 1 + q2; pnl = tp
    else: q = end; pnl = side * (float(a["c"][end]) / e - 1)
    return pnl - 0.001 - side * fund(s, t[j] + 900, t[q] + 900)
rows = []
for x in P.itertuples():
    c = strip(x.s); d = load(c, x.t)
    if d is None: continue
    a = K[x.s]; t = a["t"]; j = np.searchsorted(t, x.t - 900)
    if j >= len(t) or t[j] != x.t - 900 or j < 100: continue
    qv = a["qv"].astype(np.float64)
    first = min(d) if d else None
    if not d or first > x.t - 24 * 3600: rows.append(dict(s=x.s, t=x.t, has=False)); continue   # пары ещё не было / нет данных
    v = np.array([d.get(int(t[k]), (0.0, np.nan))[0] for k in range(j - 99, j + 1)])           # 100 свечей по 15 мин до пампа
    f = qv[j - 99:j + 1]
    h_v = v[-96:].reshape(24, 4).sum(1); h_f = f[-96:].reshape(24, 4).sum(1); sh_h = h_v / np.maximum(h_v + h_f, 1)
    share = sh_h[-1]; norm = np.median(sh_h[:-1])
    pc = d.get(int(t[j]), (0, np.nan))[1]; prem = pc / float(a["c"][j]) - 1 if pc == pc else np.nan
    rows.append(dict(s=x.s, t=x.t, has=True, share=share, norm=norm, x=share / max(norm, 1e-4), prem=prem, vol=h_v[-1],
                     short=x.pnl, korea=x.korea, kshare=x.kshare, fshare=x.fshare, fhas=x.has,
                     l30=trade(x.s, j, 1, 0.3, 0.15, 192), l10=trade(x.s, j, 1, 0.1, 0.1, 96), r4=float(a["c"][min(j + 16, len(t) - 1)]) / float(a["c"][j]) - 1,
                     r24=float(a["c"][min(j + 96, len(t) - 1)]) / float(a["c"][j]) - 1))
D = pd.DataFrame(rows); D["y"] = np.where(D.t < CUT, 1, 2); D.to_pickle(f"s5/pump_{V}.pkl")
H = D[D.has]
print(f"пампов с данными {V}: {len(H)} из {len(D)}; доля: медиана {H.share.median():.2%}, 90-й перц. {H.share.quantile(.9):.2%}; обычная {H.norm.median():.2%}")
def show(nm, g):
    print(f"{nm:44s} {len(g):5d} | шорт {g.short.mean()*100:+.2f}% ({g[g.y==1].short.mean()*100:+.2f}/{g[g.y==2].short.mean()*100:+.2f}) | "
          f"лонг 30/15/48ч {g.l30.mean()*100:+.2f}% ({g[g.y==1].l30.mean()*100:+.2f}/{g[g.y==2].l30.mean()*100:+.2f}) | лонг 10/10/24ч {g.l10.mean()*100:+.2f}% | "
          f"4ч {g.r4.median()*100:+.1f}% 24ч {g.r24.median()*100:+.1f}%")
show("все с парой", H)
for lo, hi in ((0, 0.01), (0.01, 0.03), (0.03, 0.07), (0.07, 0.15), (0.15, 1.01)):
    show(f"доля {lo:.0%}–{hi:.0%}", H[(H.share >= lo) & (H.share < hi)])
print("--- к обычной доле:")
for lo, hi in ((0, 0.5), (0.5, 1), (1, 2), (2, 4), (4, 1e9)):
    show(f"× обычной {lo:g}–{hi:g}", H[(H.x >= lo) & (H.x < hi)])
print("--- премия цены площадки к фьючерсу:")
for lo, hi in ((-1, -0.01), (-0.01, -0.002), (-0.002, 0.002), (0.002, 0.01), (0.01, 1)):
    show(f"премия {lo:+.1%}…{hi:+.1%}", H[(H.prem >= lo) & (H.prem < hi)])
noKT = ~(H.korea & (H.kshare >= 0.2)) & ~(H.fhas & (H.fshare >= 0.1))
print("--- без корейского и турецкого сигнала:")
for lo, hi in ((0, 0.01), (0.01, 0.03), (0.03, 0.07), (0.07, 1.01)):
    show(f"доля {lo:.0%}–{hi:.0%}", H[noKT & (H.share >= lo) & (H.share < hi)])
