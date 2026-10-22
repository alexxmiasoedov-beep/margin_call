"""Ежедневная панель для проверки устойчивости фактора займа: вход каждый день в 01:00 UTC, признаки канала за 3/7/14 дней,
доходности на 1/3/7/14 дней вперёд с фандингом. Выход: s10/daily_panel.pkl."""
import pickle, re, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); FU = pickle.load(open("s2/fund2y.pkl", "rb"))
m = pickle.load(open("s7/margin.pkl", "rb")); G, PT = m["G"], np.sort(np.array(m["PT"]))
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
ch = {}
for c, arr in G.items(): ch.setdefault(strip(c), []).append(np.unique(arr[:, 0]))
ch = {k: np.unique(np.concatenate(v)) for k, v in ch.items()}
UTC = datetime.timezone.utc
T = np.arange(datetime.datetime(2025, 3, 10, 1, tzinfo=UTC).timestamp(), datetime.datetime(2026, 10, 4, 1, tzinfo=UTC).timestamp(), 86400).astype(np.int64)
H = (1, 3, 7, 14); LOOK = (3, 7, 14)
npost = {L: np.searchsorted(PT, T - 3600) - np.searchsorted(PT, T - 3600 - L * 86400) for L in LOOK}
out = []
for s, a in K.items():
    t = a["t"]; j = np.searchsorted(t, T); ok = (j < len(t)) & (j >= 2900)
    ok[ok] &= t[j[ok]] == T[ok]
    if not ok.any(): continue
    o = a["o"].astype(float); qv = np.r_[0, np.cumsum(a["qv"].astype(float))]
    f = FU.get(s)
    cf = (lambda ff: (ff[:, 0], np.r_[0, np.cumsum(ff[:, 2])], ff[:, 2] / ff[:, 1] * 8))(f) if f is not None else None
    def fsum(a0, b0):
        if cf is None: return np.zeros(len(a0))
        return cf[1][np.searchsorted(cf[0], b0, "right")] - cf[1][np.searchsorted(cf[0], a0, "right")]
    jj = j[ok]; TT = T[ok]
    v7 = (qv[jj] - qv[jj - 672]) / 7
    d = dict(T=TT, s=s, v=v7, r7=o[jj] / o[jj - 672] - 1, vol=np.array([np.diff(np.log(a["c"][x - 673:x].astype(float))).std() * np.sqrt(96) for x in jj]))
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
    for L in LOOK:
        idx = np.searchsorted(T, TT)
        d[f"sh{L}"] = ((np.searchsorted(tt, TT - 3600) - np.searchsorted(tt, TT - 3600 - L * 86400)) / np.maximum(npost[L][idx], 1)) if tt is not None else np.zeros(len(TT))
    d["seen90"] = ((np.searchsorted(tt, TT - 3600) - np.searchsorted(tt, TT - 3600 - 90 * 86400)) > 0) if tt is not None else np.zeros(len(TT), bool)
    out.append(pd.DataFrame(d))
D = pd.concat(out, ignore_index=True)
D = D[D.v >= 3e6].reset_index(drop=True)
D.to_pickle("s10/daily_panel.pkl"); print("строк", len(D), "дней", D["T"].nunique(), "монет", D.s.nunique())
