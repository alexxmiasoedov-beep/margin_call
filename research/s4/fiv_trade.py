import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb")); D = pd.read_pickle("s4/fiv.pkl")
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
def trade(s, t1, side, tp, sl, hold):
    a = K[s]; t = a["t"]; j = np.searchsorted(t, t1 - 900); e = float(a["c"][j]); end = min(j + hold, len(t) - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64); lo = a["l"][j + 1:end + 1].astype(np.float64)
    if side > 0: ks = np.flatnonzero(lo <= e * (1 - sl)); kt = np.flatnonzero(hi >= e * (1 + tp))
    else: ks = np.flatnonzero(hi >= e * (1 + sl)); kt = np.flatnonzero(lo <= e * (1 - tp))
    q1 = ks[0] if len(ks) else 10**9; q2 = kt[0] if len(kt) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; pnl = -sl
    elif q2 < 10**9: q = j + 1 + q2; pnl = tp
    else: q = end; pnl = side * (float(a["c"][end]) / e - 1)
    fr = F[s]; ft = np.round(fr[:, 0].astype(np.float64) / 3600) * 3600
    m = (ft > t1) & (ft <= t[q] + 900); fd = -side * float(fr[m, 2].astype(np.float64).sum())
    return pnl - 0.001 + fd, fd
E = D[(D.kind == "короче") & (D.rate < 0)].copy()
print("событий", len(E), "монет", E.s.nunique())
for side, nm in ((1, "ЛОНГ"), (-1, "ШОРТ")):
    for tp, sl, hold in ((0.1, 0.1, 96), (0.2, 0.15, 288), (0.3, 0.2, 672), (0.5, 0.25, 672), (9, 0.3, 288), (9, 9, 96), (9, 9, 288)):
        r = [trade(x.s, x.t, side, tp, sl, hold) for x in E.itertuples()]
        p = np.array([a for a, b in r]); fd = np.array([b for a, b in r]); y = E.y.values
        print(f"{nm} тейк {tp:.0%} стоп {sl:.0%} {hold/96:.0f} дн: {p.mean()*100:+.2f}% (1-й {p[y==1].mean()*100:+.2f}, 2-й {p[y==2].mean()*100:+.2f}), "
              f"медиана {np.median(p)*100:+.1f}, в плюсе {(p>0).mean():.0%}, фандинг {fd.mean()*100:+.2f}%")
