"""Панель «монета × каждые 4 ч» за 2 года: признаки только из прошлого, исходы — из будущего (для проверки гипотез).
Цена — закрытия 15-мин свечей; d — дисбаланс тейкеров (покупки − продажи) / объём; фандинг — выплаты из архива."""
import pickle, datetime
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as sw
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
UTC = datetime.timezone.utc
T0 = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); T1 = datetime.datetime(2026, 10, 18, tzinfo=UTC).timestamp()
def roll(x, w):                                   # сумма за последние w свечей, включая текущую
    cs = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)]); out = np.full(len(x), np.nan); out[w - 1:] = cs[w:] - cs[:-w]; return out
B = K["BTC"]; bt = {int(t): i for i, t in enumerate(B["t"])}; bc = B["c"].astype(np.float64)
rows = []
for s, a in K.items():
    t = a["t"]; c = a["c"].astype(np.float64); h = a["h"].astype(np.float64); l = a["l"].astype(np.float64)
    qv = a["qv"].astype(np.float64); tb = a["tb"].astype(np.float64); n = len(t)
    if n < 96 * 8: continue
    first = t[0]
    end = t + 900
    sel = np.flatnonzero((end % 14400 == 0) & (end >= T0) & (end <= T1))
    sel = sel[(sel >= 96 * 3) & (sel < n - 96 * 3)]
    if not len(sel): continue
    q4, q24, q7d = roll(qv, 16), roll(qv, 96), roll(qv, 672)
    b4, b24 = roll(tb, 16), roll(tb, 96)
    hh24 = np.full(n, np.nan); ll24 = np.full(n, np.nan); hh24[95:] = sw(h, 96).max(1); ll24[95:] = sw(l, 96).min(1)
    fmax24 = np.full(n, np.nan); fmin24 = np.full(n, np.nan); fmax24[:n - 96] = sw(h[1:], 96).max(1)[:n - 96]; fmin24[:n - 96] = sw(l[1:], 96).min(1)[:n - 96]
    fr = F.get(s)
    def fsum(t_a, t_b):
        if fr is None: return np.zeros(len(t_a))
        cs = np.concatenate([[0.0], np.cumsum(fr[:, 2])]); ia = np.searchsorted(fr[:, 0], t_a, "right"); ib = np.searchsorted(fr[:, 0], t_b, "right")
        return cs[ib] - cs[ia]
    te = end[sel].astype(np.float64)
    bi = np.array([bt.get(int(x), -1) for x in t[sel]])
    okb = bi >= 96
    btc4 = np.where(okb, bc[np.clip(bi, 0, None)] / bc[np.clip(bi - 16, 0, None)] - 1, np.nan)
    btc24 = np.where(okb, bc[np.clip(bi, 0, None)] / bc[np.clip(bi - 96, 0, None)] - 1, np.nan)
    d = dict(s=np.full(len(sel), s), t=te, age=(te - first) / 86400,
             r1=c[sel] / c[sel - 4] - 1, r4=c[sel] / c[sel - 16] - 1, r24=c[sel] / c[sel - 96] - 1, r72=c[sel] / c[sel - 288] - 1,
             d4=(2 * b4[sel] - q4[sel]) / np.maximum(q4[sel], 1), d24=(2 * b24[sel] - q24[sel]) / np.maximum(q24[sel], 1),
             v24=q24[sel], volr=q24[sel] / np.maximum(q7d[sel] / 7, 1), rng24=hh24[sel] / ll24[sel] - 1, fromhi=c[sel] / hh24[sel] - 1,
             fromlo=c[sel] / ll24[sel] - 1, fund72=fsum(te - 72 * 3600, te), fund24=fsum(te - 24 * 3600, te),
             btc4=btc4, btc24=btc24,
             f4=c[sel + 16] / c[sel] - 1, f24=c[sel + 96] / c[sel] - 1, f72=c[sel + 288] / c[sel] - 1,
             fmax24=fmax24[sel] / c[sel] - 1, fmin24=fmin24[sel] / c[sel] - 1, ffund24=fsum(te, te + 24 * 3600), ffund72=fsum(te, te + 72 * 3600))
    rows.append(pd.DataFrame(d))
P = pd.concat(rows, ignore_index=True)
for col in P.columns:
    if P[col].dtype == np.float64: P[col] = P[col].astype(np.float32)
P.to_pickle("s2/panel.pkl"); print("строк", len(P), "| монет", P.s.nunique(), "| с", datetime.datetime.fromtimestamp(P.t.min(), UTC), "по", datetime.datetime.fromtimestamp(P.t.max(), UTC))
