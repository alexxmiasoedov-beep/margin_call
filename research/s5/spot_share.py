"""Доля спота Binance (пара к USDT) в объёме за час на момент пампа и её обычная доля (медиана часовых долей за 7 суток),
доля покупок тейкеров на споте и на фьючерсе. Исходы: шорт 10/25/48 ч (как в корейском правиле), лонг 30/15/48 ч."""
import pickle, re, os, datetime
import numpy as np, pandas as pd
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb")); P = pd.read_pickle("s2/pump_TRY.pkl")
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
src = open("s5/venue_share.py").read(); exec("def fund(" + src.split("def fund(")[1].split("rows = []")[0])
SP = {}
for s in set(P.s):
    for n in (s, strip(s)):
        fn = f"s5/spot/{n}USDT.npy"
        if os.path.exists(fn):
            a = np.load(fn)
            if len(a): SP[s] = a; break
rows = []
for x in P.itertuples():
    a = K[x.s]; t = a["t"]; j = np.searchsorted(t, x.t - 900)
    if j >= len(t) or t[j] != x.t - 900 or j < 700: continue
    b = SP.get(x.s)
    if b is None or b[0, 0] > x.t - 8 * 86400: rows.append(dict(s=x.s, t=x.t, has=False, short=x.pnl)); continue
    tt = t[j - 671:j + 1]; ix = np.searchsorted(b[:, 0], tt); okk = ix < len(b); okk[okk] &= b[ix[okk], 0] == tt[okk]
    sv = np.zeros(672); stb = np.zeros(672); sv[okk] = b[ix[okk], 2]; stb[okk] = b[ix[okk], 3]
    fv = a["qv"][j - 671:j + 1].astype(np.float64); ftb = a["tb"][j - 671:j + 1].astype(np.float64) * a["c"][j - 671:j + 1].astype(np.float64)
    hs = sv.reshape(168, 4).sum(1); hf = fv.reshape(168, 4).sum(1); sh = hs / np.maximum(hs + hf, 1)
    share, norm = sh[-1], np.median(sh[:-1])
    sbuy = stb[-4:].sum() / max(sv[-4:].sum(), 1); fbuy = ftb[-4:].sum() / max(fv[-4:].sum(), 1)
    pc = b[ix[-1], 1] if okk[-1] else np.nan
    rows.append(dict(s=x.s, t=x.t, has=True, share=share, norm=norm, x=share / max(norm, 1e-4), sbuy=sbuy, fbuy=fbuy,
                     prem=pc / float(a["c"][j]) - 1, short=x.pnl, korea=x.korea, kshare=x.kshare, fshare=x.fshare, fhas=x.has,
                     l30=trade(x.s, j, 1, 0.3, 0.15, 192), s1015=trade(x.s, j, -1, 0.1, 0.15, 96)))
D = pd.DataFrame(rows); D["y"] = np.where(D.t < CUT, 1, 2); D.to_pickle("s5/pump_spot.pkl")
H = D[D.has]
print(f"пампов со спотом: {len(H)} из {len(D)}; доля спота: медиана {H.share.median():.1%}, обычная {H.norm.median():.1%}; × обычной медиана {H.x.median():.2f}")
def show(nm, g):
    print(f"{nm:40s} {len(g):5d} | шорт 10/25/48 {g.short.mean()*100:+.2f}% ({g[g.y==1].short.mean()*100:+.2f}/{g[g.y==2].short.mean()*100:+.2f}) | "
          f"шорт 10/15/24 {g.s1015.mean()*100:+.2f}% ({g[g.y==1].s1015.mean()*100:+.2f}/{g[g.y==2].s1015.mean()*100:+.2f}) | лонг 30/15/48 {g.l30.mean()*100:+.2f}% ({g[g.y==1].l30.mean()*100:+.2f}/{g[g.y==2].l30.mean()*100:+.2f})")
show("все со спотом", H); show("нет спота", D[~D.has])
for lo, hi in ((0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.45), (0.45, 1.01)):
    show(f"доля спота {lo:.0%}–{hi:.0%}", H[(H.share >= lo) & (H.share < hi)])
for lo, hi in ((0, 0.7), (0.7, 1), (1, 1.5), (1.5, 2.5), (2.5, 1e9)):
    show(f"× обычной {lo:g}–{hi:g}", H[(H.x >= lo) & (H.x < hi)])
for lo, hi in ((0, 0.45), (0.45, 0.5), (0.5, 0.55), (0.55, 0.6), (0.6, 1.01)):
    show(f"покупки тейкеров на споте {lo:.0%}–{hi:.0%}", H[(H.sbuy >= lo) & (H.sbuy < hi)])
for lo, hi in ((-1, -0.003), (-0.003, 0.0), (0.0, 0.003), (0.003, 0.01), (0.01, 1)):
    show(f"премия спота к фьючерсу {lo:+.1%}…{hi:+.1%}", H[(H.prem >= lo) & (H.prem < hi)])
noKT = ~(H.korea & (H.kshare >= 0.2)) & ~(H.fhas & (H.fshare >= 0.1))
print("--- без корейского и турецкого сигнала:")
for lo, hi in ((0, 0.7), (0.7, 1.5), (1.5, 2.5), (2.5, 1e9)):
    show(f"× обычной {lo:g}–{hi:g}", H[noKT & (H.x >= lo) & (H.x < hi)])
