"""Признаки каждого пампа за 2 года (по свечам и фандингу, всё до входа) + итог шорта 10/25/48 ч из bt2y → s2/pumpfeat.pkl."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb")); R = pickle.load(open("mm2/bt2y.pkl", "rb"))
EV = pickle.load(open("mm2/pumps2y.pkl", "rb"))["EV"]
B = K["BTC"]; bidx = {int(t): i for i, t in enumerate(B["t"])}; bc = B["c"].astype(np.float64)
rows = []
for e, r in zip(EV, R):
    s = e["s"]; a = K[s]; t = a["t"]; T = int(e["t_in"]); j = int(np.searchsorted(t, T - 900))
    if j >= len(t) or t[j] != T - 900 or j < 700: continue
    c = a["c"].astype(np.float64); h = a["h"].astype(np.float64); l = a["l"].astype(np.float64); qv = a["qv"].astype(np.float64)
    tb = a["tb"].astype(np.float64); n = a["n"].astype(np.float64)
    i = j - (e["j"] - e["i"])                                            # базовая спокойная свеча
    pre = slice(i - 95, i + 1); pump = slice(i + 1, j + 1)
    vb = qv[pre].mean() + 1e-9; nb = n[pre].mean() + 1e-9
    d = dict(s=s, t=T, korea=r["korea"], share=r["share"], pnl=r["pnl_10"], pnl15=r["pnl_15"], fund=r["fund_10"],
             speed=j - i, gain_hi=h[pump].max() / c[i] - 1, gain_c=c[j] / c[i] - 1, wick=(h[pump].max() - c[j]) / (h[pump].max() - c[i] + 1e-12),
             volx=qv[pump].mean() / vb, tradesx=n[pump].mean() / nb, sizex=(qv[pump].sum() / max(n[pump].sum(), 1)) / (qv[pre].sum() / max(n[pre].sum(), 1)),
             buy=tb[pump].sum() / max(qv[pump].sum(), 1), pre24=c[i] / c[i - 96] - 1, pre7d=c[i] / c[i - 672] - 1,
             rng7d=h[i - 671:i + 1].max() / l[i - 671:i + 1].min() - 1, vol24=qv[pre].sum(), vol7x=qv[pre].sum() / (qv[i - 671:i + 1].sum() / 7 + 1e-9),
             pumps7d=sum(1 for e2 in [] if 0), age=(T - t[0]) / 86400, hour=(T // 3600) % 24, dow=pd.Timestamp(T, unit="s").dayofweek)
    fr = F.get(s)
    if fr is not None:
        k = np.searchsorted(fr[:, 0], T, "right") - 1
        if k >= 0:
            d["f_last"] = fr[k, 2]; d["f_iv"] = fr[k, 1]
            d["f_24"] = fr[(fr[:, 0] > T - 86400) & (fr[:, 0] <= T), 2].sum(); d["f_72"] = fr[(fr[:, 0] > T - 3 * 86400) & (fr[:, 0] <= T), 2].sum()
    bi = bidx.get(T - 900)
    if bi is not None and bi > 96: d["btc4"] = bc[bi] / bc[bi - 16] - 1; d["btc24"] = bc[bi] / bc[bi - 96] - 1
    rows.append(d)
D = pd.DataFrame(rows); D["year"] = pd.to_datetime(D.t, unit="s").dt.year; D["half"] = np.where(D.t < datetime.datetime(2025, 10, 1, tzinfo=datetime.timezone.utc).timestamp(), "1-й год", "2-й год")
D.to_pickle("s2/pumpfeat.pkl"); print("пампов с признаками", len(D), "| не в Корее", (~D.korea).sum())
