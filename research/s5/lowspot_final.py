"""Лонг «памп без розницы» — итоговые правила A (строгое) и B (широкое): месяцы, просадка, одновременные позиции, фандинг,
концентрация, исходы; сделки по МСК в s5/lowspot_<правило>.pkl."""
import pickle, datetime
import numpy as np, pandas as pd
src = open("s5/venue_share.py").read()
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
exec("def fund(" + src.split("def fund(")[1].split("rows = []")[0])
def trade2(s, j, tp, sl, hold):
    a = K[s]; t = a["t"]; e = float(a["c"][j]); end = min(j + hold, len(t) - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64); lo = a["l"][j + 1:end + 1].astype(np.float64)
    ks = np.flatnonzero(lo <= e * (1 - sl)); kt = np.flatnonzero(hi >= e * (1 + tp))
    q1 = ks[0] if len(ks) else 10**9; q2 = kt[0] if len(kt) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; px = -sl; how = "стоп"
    elif q2 < 10**9: q = j + 1 + q2; px = tp; how = "тейк"
    else: q = end; px = float(a["c"][end]) / e - 1; how = "время"
    fd = -fund(s, t[j] + 900, t[q] + 900)
    return px - 0.001 + fd, fd, how, t[q] + 900
H = pd.read_pickle("s5/lowspot_tt.pkl")
ks = H.kshare.fillna(0).where(H.korea, 0); fs = H.fshare.fillna(0).where(H.fhas, 0)
for nm, X, KR, TR in (("A", 0.10, 0.10, 0.05), ("B", 0.12, 0.20, 0.10)):
    g = H[(H.share < X) & (ks < KR) & (fs < TR)].copy()
    r = [trade2(s, j, 0.3, 0.15, 192) for s, j in zip(g.s, g.j)]
    g["p"] = [x[0] for x in r]; g["fund"] = [x[1] for x in r]; g["how"] = [x[2] for x in r]; g["out"] = [x[3] for x in r]
    g = g.sort_values("t"); u = g.p.values * 10; eq = np.cumsum(u); dd = (eq - np.maximum.accumulate(eq)).min()
    ev = sorted([(t, 1) for t in g.t] + [(t, -1) for t in g.out]); cur = mx = 0
    for _, x in ev: cur += x; mx = max(mx, cur)
    mo = g.groupby(pd.to_datetime(g.t, unit="s").dt.strftime("%y-%m")).p.sum() * 10
    bys = g.groupby("s").p.sum().sort_values(ascending=False); top = set(bys.index[:max(1, len(bys) // 20)]); srt = g.p.sort_values(ascending=False)
    print(f"\n=== правило {nm}: доля спота < {X:.0%}, Корея < {KR:.0%}, лира < {TR:.0%}; тейк 30 / стоп 15 / 48 ч")
    print(f"{len(g)} сделок, {g.s.nunique()} монет, {g.p.mean()*100:+.2f}% на сделку (1-й год {g[g.y==1].p.mean()*100:+.2f}, 2-й {g[g.y==2].p.mean()*100:+.2f}), в плюсе {(g.p>0).mean():.0%}, "
          f"итог {u.sum():+.1f} USDT, просадка {dd:+.1f}, одновременно до {mx}, фандинг {g.fund.mean()*100:+.2f}% на сделку")
    print(f"исходы: " + ", ".join(f"{k} {v}" for k, v in g.how.value_counts().items()) + f" | без 1% лучших сделок {srt.iloc[len(g)//100:].mean()*100:+.2f}%, без 5% лучших монет {g[~g.s.isin(top)].p.mean()*100:+.2f}%, монет в плюсе {(bys>0).sum()}/{len(bys)}")
    print(f"месяцев в плюсе {(mo>0).sum()}/{len(mo)}: " + " ".join(f"{k}:{v:+.1f}" for k, v in mo.items()))
    g["msk"] = pd.to_datetime(g.t + 3 * 3600, unit="s").dt.strftime("%d.%m.%Y %H:%M")
    g[["s", "t", "msk", "share", "norm", "kshare", "fshare", "p", "fund", "how", "out"]].to_pickle(f"s5/lowspot_{nm}.pkl")
