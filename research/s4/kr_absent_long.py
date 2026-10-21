"""Лонг пампа, в котором корейцев ещё нет: монета торгуется на Upbit/Bithumb, но их доля в объёме за час < 5% (и турок нет).
Гипотеза: корейская розница — ликвидность для выхода; если её ещё нет, памп не закончен. 2 года, комиссия 0,1%, фандинг по факту."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb")); P = pd.read_pickle("s2/pump_TRY.pkl")
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
def fund(s, a, b):
    fr = F.get(s)
    if fr is None: return 0.0
    ft = fr[:, 0].astype(np.float64); m = (ft > a) & (ft <= b); return float(fr[m, 2].astype(np.float64).sum())
def trade(s, t_in, side, tp, sl, hold):
    a = K[s]; t = a["t"]; j = np.searchsorted(t, t_in - 900)
    if j >= len(t) or t[j] != t_in - 900: return np.nan
    e = float(a["c"][j]); end = min(j + hold, len(t) - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64); lo = a["l"][j + 1:end + 1].astype(np.float64)
    if side > 0: ks = np.flatnonzero(lo <= e * (1 - sl)); kt = np.flatnonzero(hi >= e * (1 + tp))
    else: ks = np.flatnonzero(hi >= e * (1 + sl)); kt = np.flatnonzero(lo <= e * (1 - tp))
    q1 = ks[0] if len(ks) else 10**9; q2 = kt[0] if len(kt) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; pnl = -sl
    elif q2 < 10**9: q = j + 1 + q2; pnl = tp
    else: q = end; pnl = side * (float(a["c"][end]) / e - 1)
    return pnl - 0.001 - side * fund(s, t_in, t[q] + 900)
P["y"] = np.where(P.t < CUT, 1, 2)
G = {"монета в Корее, доля < 5%": P[P.korea & (P.kshare < 0.05)],
     "то же и без турок (доля лиры < 3% или пары нет)": P[P.korea & (P.kshare < 0.05) & ~(P.has & (P.fshare >= 0.03))],
     "монеты нет в Корее": P[~P.korea],
     "нет в Корее и без турок": P[~P.korea & ~(P.has & (P.fshare >= 0.03))],
     "все пампы": P}
for nm, g in G.items():
    print(f"\n{nm}: {len(g)}")
    for tp, sl, hold in ((0.1, 0.1, 96), (0.15, 0.1, 192), (0.2, 0.15, 192), (0.3, 0.15, 192), (0.3, 0.2, 288), (9, 9, 16), (9, 9, 96), (9, 9, 192)):
        p = np.array([trade(x.s, x.t, 1, tp, sl, hold) for x in g.itertuples()]); y = g.y.values; ok = ~np.isnan(p)
        print(f"  ЛОНГ {tp:.0%}/{sl:.0%}/{hold/4:.0f} ч: {np.nanmean(p)*100:+.2f}% (1-й {np.nanmean(p[ok & (y==1)])*100:+.2f}, 2-й {np.nanmean(p[ok & (y==2)])*100:+.2f}), в плюсе {(p[ok]>0).mean():.0%}")
