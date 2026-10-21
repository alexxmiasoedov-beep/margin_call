"""Расширенная панель «монета × каждый час» за 2 года (признаки — только прошлое; исходы — будущее) для поиска связей моделью."""
import pickle, datetime
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as sw
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
X = pickle.load(open("s2/fiat_TRY.pkl", "rb")); TP, TD = X["pairs"], X["D"]; fx = TD["USDTTRY"]
UTC = datetime.timezone.utc
T0 = datetime.datetime(2024, 10, 26, tzinfo=UTC).timestamp(); T1 = datetime.datetime(2026, 10, 15, tzinfo=UTC).timestamp()
def roll(x, w):
    cs = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)]); out = np.full(len(x), np.nan); out[w - 1:] = cs[w:] - cs[:-w]; return out
def rmax(x, w):
    o = np.full(len(x), np.nan); o[w - 1:] = sw(x, w).max(1); return o
def rmin(x, w):
    o = np.full(len(x), np.nan); o[w - 1:] = sw(x, w).min(1); return o
B = K["BTC"]; bt = {int(t): i for i, t in enumerate(B["t"])}; bc = B["c"].astype(np.float64)
parts = []
for s, a in K.items():
    t = a["t"]; n = len(t)
    if n < 96 * 9: continue
    c = a["c"].astype(np.float64); h = a["h"].astype(np.float64); l = a["l"].astype(np.float64)
    qv = a["qv"].astype(np.float64); tb = a["tb"].astype(np.float64); nt = a["n"].astype(np.float64)
    end = t + 900; sel = np.flatnonzero((end % 3600 == 0) & (end >= T0) & (end <= T1))
    sel = sel[(sel >= 673) & (sel < n - 97)]
    if not len(sel): continue
    q1, q4, q24, q7 = roll(qv, 4), roll(qv, 16), roll(qv, 96), roll(qv, 672)
    b1, b4, b24 = roll(tb, 4), roll(tb, 16), roll(tb, 96); n4, n7 = roll(nt, 16), roll(nt, 672)
    hi24, lo24, hi7, lo7 = rmax(h, 96), rmin(l, 96), rmax(h, 672), rmin(l, 672)
    fmx = np.full(n, np.nan); fmn = np.full(n, np.nan); fmx[:n - 96] = sw(h[1:], 96).max(1)[:n - 96]; fmn[:n - 96] = sw(l[1:], 96).min(1)[:n - 96]
    fr = F.get(s)
    def fsum(ta, tb_):
        if fr is None: return np.zeros(len(ta))
        cs = np.concatenate([[0.0], np.cumsum(fr[:, 2])]); return cs[np.searchsorted(fr[:, 0], tb_, "right")] - cs[np.searchsorted(fr[:, 0], ta, "right")]
    te = end[sel].astype(np.float64)
    fl = np.full(len(sel), np.nan); fiv = np.full(len(sel), np.nan)
    if fr is not None:
        k = np.searchsorted(fr[:, 0], te, "right") - 1; ok = k >= 0; fl[ok] = fr[k[ok], 2]; fiv[ok] = fr[k[ok], 1]
    tsh1 = np.full(len(sel), np.nan); tsh24 = np.full(len(sel), np.nan)
    if s in TP and f"{TP[s]}TRY" in TD:                                   # турецкая доля: час и сутки
        b = TD[f"{TP[s]}TRY"]; tv = np.zeros(n); ix = np.searchsorted(t, b[:, 0]); ok = ix < n; ok[ok] &= t[ix[ok]] == b[ok, 0]
        tv[ix[ok]] = b[ok, 2] / np.interp(b[ok, 0], fx[:, 0], fx[:, 1]); tq1, tq24 = roll(tv, 4), roll(tv, 96)
        live = t[sel] > b[0, 0] + 7 * 86400
        tsh1 = np.where(live, tq1[sel] / np.maximum(tq1[sel] + q1[sel], 1), np.nan); tsh24 = np.where(live, tq24[sel] / np.maximum(tq24[sel] + q24[sel], 1), np.nan)
    bi = np.array([bt.get(int(x), -1) for x in t[sel]]); okb = bi >= 96; bic = np.clip(bi, 96, None)
    d = dict(s=np.full(len(sel), s), t=end[sel].astype(np.int64), age=(te - t[0]) / 86400,
             r1=c[sel] / c[sel - 4] - 1, r4=c[sel] / c[sel - 16] - 1, r24=c[sel] / c[sel - 96] - 1, r7d=c[sel] / c[sel - 672] - 1,
             d1=(2 * b1[sel] - q1[sel]) / np.maximum(q1[sel], 1), d4=(2 * b4[sel] - q4[sel]) / np.maximum(q4[sel], 1), d24=(2 * b24[sel] - q24[sel]) / np.maximum(q24[sel], 1),
             v24=q24[sel], vx=q24[sel] / np.maximum((q7[sel] - q24[sel]) / 6, 1), v1x=q1[sel] * 24 / np.maximum(q24[sel], 1),
             tsz=(q4[sel] / np.maximum(n4[sel], 1)) / np.maximum(q7[sel] / np.maximum(n7[sel], 1), 1e-9), nrate=n4[sel] / np.maximum(n7[sel] / 42, 1),
             rng24=hi24[sel] / lo24[sel] - 1, rng7=hi7[sel] / lo7[sel] - 1, fromhi24=c[sel] / hi24[sel] - 1, fromlo24=c[sel] / lo24[sel] - 1,
             fromhi7=c[sel] / hi7[sel] - 1, fromlo7=c[sel] / lo7[sel] - 1, fund24=fsum(te - 86400, te), fund72=fsum(te - 3 * 86400, te), flast=fl, fiv=fiv,
             tsh1=tsh1, tsh24=tsh24, tshx=tsh1 / np.maximum(tsh24, 1e-4),
             btc4=np.where(okb, bc[bic] / bc[bic - 16] - 1, np.nan), btc24=np.where(okb, bc[bic] / bc[bic - 96] - 1, np.nan),
             hour=((te // 3600) % 24), dow=((te // 86400 + 3) % 7),
             f24=c[sel + 96] / c[sel] - 1, ffund24=fsum(te, te + 86400), fmax24=fmx[sel] / c[sel] - 1, fmin24=fmn[sel] / c[sel] - 1)
    parts.append(pd.DataFrame(d))
P = pd.concat(parts, ignore_index=True)
for col in P.columns:
    if P[col].dtype == np.float64: P[col] = P[col].astype(np.float32)
P = P[P.v24 >= 3e6].reset_index(drop=True)
g = P.groupby("t")
P["mkt24"] = g.r24.transform("mean"); P["breadth"] = g.r24.transform(lambda x: (x > 0.1).mean()); P["f24m"] = P.f24 - g.f24.transform("mean")
P["r24_rank"] = g.r24.rank(pct=True); P["vx_rank"] = g.vx.rank(pct=True); P["fund24_rank"] = g.fund24.rank(pct=True)
P.to_pickle("s3/panel2.pkl"); print("строк", len(P), "| монет", P.s.nunique(), "| признаков", P.shape[1])
