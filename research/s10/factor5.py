"""Не сводится ли фактор займа к ценовым факторам? Для каждой недели и монеты — признаки, известные на входе:
доходность за 1/7/30 дней, волатильность, максимум дневного роста за неделю (эффект «лотереи»), рост объёма, фандинг,
доля покупок тейкеров, ликвидность — плюс признаки канала MarginData за 7 дней. Регрессии Фамы–Макбета по рангам
и двойные сортировки. Выход: s10/factor5.pkl."""
import pickle, re, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); FU = pickle.load(open("s2/fund2y.pkl", "rb"))
m = pickle.load(open("s7/margin.pkl", "rb")); G, PT = m["G"], np.array(m["PT"])
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
GG = {}
for c, arr in G.items(): GG.setdefault(strip(c), []).append(arr)
GG = {k: (lambda a: a[np.argsort(a[:, 0])])(np.vstack(v)) for k, v in GG.items()}
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()
start = datetime.datetime(2025, 3, 10, tzinfo=UTC).timestamp(); end = datetime.datetime(2026, 9, 7, tzinfo=UTC).timestamp()
def fsum(s, a, b):
    f = FU.get(s)
    if f is None: return 0.0
    return float(f[np.searchsorted(f[:, 0], a, "right"):np.searchsorted(f[:, 0], b, "right"), 2].sum())
def fnow(s, t):
    f = FU.get(s)
    if f is None: return np.nan
    k = np.searchsorted(f[:, 0], t, "right") - 1; return float(f[k, 2] / f[k, 1] * 8) if k >= 0 else np.nan
rows = []
for W in np.arange(start, end, 7 * 86400):
    n_posts = ((PT >= W - 7 * 86400) & (PT < W)).sum()
    for s, a in K.items():
        t = a["t"]; j = int(np.searchsorted(t, int(W + 3600)))
        if j < 2900 or j + 672 >= len(t) or t[j] != W + 3600 or t[j + 672] != W + 7 * 86400 + 3600: continue
        qv = a["qv"][j - 2880:j].astype(float); v = qv[-672:].sum() / 7
        if v < 3e6: continue
        o, c = a["o"].astype(float), a["c"][j - 2880:j].astype(float)
        e, x = o[j], o[j + 672]
        lr = np.diff(np.log(c[-673:])); d = c[-673::96]
        row = dict(W=W, s=s, v=v, ret=x / e - 1, fr=fsum(s, W + 3600, W + 7 * 86400 + 3600), f0=fnow(s, W), fr7=fsum(s, W - 6 * 86400, W + 3600),
                   r1=e / o[j - 96] - 1, r7=e / o[j - 672] - 1, r30=e / o[j - 2880] - 1, vol=lr.std() * np.sqrt(96),
                   mx=(d[1:] / d[:-1] - 1).max(), vchg=v / (qv.sum() / 30), tbr=float(a["tb"][j - 672:j].astype(float).sum()) / max(qv[-672:].sum(), 1))
        g = GG.get(strip(s)); sh = 0.0; bor = br = np.nan
        if g is not None:
            k0, k1 = np.searchsorted(g[:, 0], W - 7 * 86400), np.searchsorted(g[:, 0], W)
            if k1 > k0:
                sh = len(np.unique(g[k0:k1, 0])) / n_posts
                bor = np.median(g[k0:k1, 1]) / v; br = np.median(np.log1p(np.minimum(g[k0:k1, 3], 1e3)))
        row.update(sh=sh, bor=bor, br=br); rows.append(row)
F = pd.DataFrame(rows); F.to_pickle("s10/factor5.pkl"); print("строк", len(F), "недель", F.W.nunique())
