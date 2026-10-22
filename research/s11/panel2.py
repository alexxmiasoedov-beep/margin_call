"""Ежедневная панель 01.11.2024–04.10.2026 (вход в 01:00 UTC): как s10/daily_panel.py + ставки маржи Binance
(s11/rates/*.csv — точки изменения ставки, между ними ставка держится): ставка на 00:00 UTC, средняя за 7 суток
(по часам), к медиане за 60 суток, изменение за 7 суток. Выход: s11/panel2.pkl"""
import pickle, re, datetime, os
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); FU = pickle.load(open("s2/fund2y.pkl", "rb"))
m = pickle.load(open("s7/margin.pkl", "rb")); G, PT = m["G"], np.sort(np.array(m["PT"]))
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
ch = {}
for c, arr in G.items(): ch.setdefault(strip(c), []).append(np.unique(arr[:, 0]))
ch = {k: np.unique(np.concatenate(v)) for k, v in ch.items()}
R = {}
for fn in os.listdir("s11/rates"):
    if fn.endswith(".csv") and os.path.getsize(f"s11/rates/{fn}") > 0:
        a = np.loadtxt(f"s11/rates/{fn}", delimiter=",", ndmin=2)
        if len(a): R.setdefault(strip(fn[:-4]), []).append(a)
R = {k: (lambda a: a[np.argsort(a[:, 0])])(np.vstack(v)) for k, v in R.items()}
print("активов со ставками", len(R), flush=True)
UTC = datetime.timezone.utc
T = np.arange(datetime.datetime(2024, 11, 1, 1, tzinfo=UTC).timestamp(), datetime.datetime(2026, 10, 4, 1, tzinfo=UTC).timestamp(), 86400).astype(np.int64)
H = (1, 3, 7, 14); LOOK = (7,)
npost = {L: np.searchsorted(PT, T - 3600) - np.searchsorted(PT, T - 3600 - L * 86400) for L in LOOK}
END = max(r[-1, 0] for r in R.values())
def rate_at(r, t):                              # ставка, действующая в момент t (последняя точка изменения ≤ t)
    k = np.searchsorted(r[:, 0], t, "right") - 1
    v = np.where(k >= 0, r[np.maximum(k, 0), 1], np.nan)
    if r[-1, 0] < END - 3 * 86400:              # история кончилась раньше — актив убран из маржи: дальше ставки нет
        v = np.where(t > r[-1, 0] + 2 * 86400, np.nan, v)
    return v
out = []
for s, a in K.items():
    t = a["t"]; j = np.searchsorted(t, T); ok = (j < len(t)) & (j >= 2900)
    ok[ok] &= t[j[ok]] == T[ok]
    if not ok.any(): continue
    o = a["o"].astype(float); qv = np.r_[0, np.cumsum(a["qv"].astype(float))]
    f = FU.get(s)
    cf = (f[:, 0], np.r_[0, np.cumsum(f[:, 2])], f[:, 2] / f[:, 1] * 8) if f is not None else None
    def fsum(a0, b0):
        if cf is None: return np.zeros(len(a0))
        return cf[1][np.searchsorted(cf[0], b0, "right")] - cf[1][np.searchsorted(cf[0], a0, "right")]
    jj = j[ok]; TT = T[ok]
    d = dict(T=TT, s=s, v=(qv[jj] - qv[jj - 672]) / 7, r7=o[jj] / o[jj - 672] - 1, r1=o[jj] / o[jj - 96] - 1,
             vol=np.array([np.diff(np.log(a["c"][x - 673:x].astype(float))).std() * np.sqrt(96) for x in jj]))
    if cf is not None:
        k = np.searchsorted(cf[0], TT - 3600, "right") - 1; d["f0"] = np.where(k >= 0, cf[2][np.maximum(k, 0)], np.nan)
    else: d["f0"] = np.full(len(TT), np.nan)
    d["fr7p"] = fsum(TT - 7 * 86400, TT)
    for h in H:
        jx = jj + 96 * h; okx = jx < len(t)
        okx[okx] &= t[np.minimum(jx[okx], len(t) - 1)] == TT[okx] + h * 86400
        d[f"ret{h}"] = np.where(okx, o[np.minimum(jx, len(t) - 1)] / o[jj] - 1, np.nan)
        d[f"fr{h}"] = fsum(TT, TT + h * 86400)
    tt = ch.get(strip(s))
    idx = np.searchsorted(T, TT)
    d["sh7"] = ((np.searchsorted(tt, TT - 3600) - np.searchsorted(tt, TT - 3600 - 7 * 86400)) / np.maximum(npost[7][idx], 1)) if tt is not None else np.zeros(len(TT))
    d["seen90"] = ((np.searchsorted(tt, TT - 3600) - np.searchsorted(tt, TT - 3600 - 90 * 86400)) > 0) if tt is not None else np.zeros(len(TT), bool)
    r = R.get(strip(s))
    if r is not None:
        c0 = TT - 3600
        d["rate0"] = rate_at(r, c0)
        hrs = c0[:, None] - 3600 * np.arange(0, 168)[None, :]
        d["rate7"] = np.nanmean(rate_at(r, hrs.ravel()).reshape(hrs.shape), axis=1)
        hrs60 = c0[:, None] - 3600 * np.arange(0, 60 * 24, 6)[None, :]
        d["rate60m"] = np.nanmedian(rate_at(r, hrs60.ravel()).reshape(hrs60.shape), axis=1)
        d["rate_7ago"] = rate_at(r, c0 - 7 * 86400)
        d["rate_first"] = np.full(len(TT), r[0, 0])
    out.append(pd.DataFrame(d))
P = pd.concat(out, ignore_index=True)
P = P[P.v >= 3e6].reset_index(drop=True)
P.to_pickle("s11/panel2.pkl"); print("строк", len(P), "дней", P["T"].nunique(), "монет", P.s.nunique(), "со ставкой", P.rate7.notna().mean().round(3) if "rate7" in P else 0, flush=True)
