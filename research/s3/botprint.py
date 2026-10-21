"""«Отпечатки ботов» в минутных свечах фьючерса за сутки до момента (памп / дамп / покой, месяц 19.09–18.10):
объём без движения цены, отклонение первых цифр объёма от закона Бенфорда, круглые объёмы, повторяющиеся размеры сделок,
ровность потока сделок. Сравнение групп (AUC) по половинам месяца; плюс всплеск за последний час против суток."""
import pickle, os, math, datetime
import numpy as np, pandas as pd, scipy.stats as st
M = pickle.load(open("mm2/moments.pkl", "rb")); K = pickle.load(open("kaia/k15_all.pkl", "rb"))
BEN = np.log10(1 + 1 / np.arange(1, 10))
MSK = datetime.timezone(datetime.timedelta(hours=3)); MID = datetime.datetime(2026, 10, 4, tzinfo=MSK).timestamp()
def first_digit(x):
    x = x[x > 0]; return (x / 10 ** np.floor(np.log10(x))).astype(int).clip(1, 9)
def feats(f):
    """f: минутки за окно (t, o, h, l, c, v, qv, n, tb)."""
    trd = f[f[:, 7] > 0]
    if len(trd) < 60: return {}
    flat = trd[:, 2] == trd[:, 3]
    fd = first_digit(trd[:, 6]); dist = np.bincount(fd, minlength=10)[1:] / len(fd)
    v = trd[:, 5]; mag = 10 ** np.floor(np.log10(np.maximum(v, 1e-12)))
    roundq = np.abs(v / mag - np.round(v / mag, 1)) < 1e-9                 # объём из двух значащих цифр (например 1,2 × 10^k)
    size = trd[:, 6] / trd[:, 7]; sz = np.round(size / 10 ** np.floor(np.log10(size)), 2)
    vals, cnt = np.unique(sz, return_counts=True)
    n = trd[:, 7]
    return dict(flat_share=trd[flat, 6].sum() / trd[:, 6].sum(), flat_min=flat.mean(), benford=np.abs(dist - BEN).sum(),
                roundq=roundq.mean(), single=(n == 1).mean(), size_mode=cnt.max() / len(sz), n_cv=n.std() / n.mean(),
                n_ac1=np.corrcoef(n[:-1], n[1:])[0, 1] if len(n) > 10 and n.std() > 0 else np.nan, dead=1 - len(trd) / max(len(f), 1))
rows = []
for g, s, i in M:
    fn = f"mm2/raw/{s}.pkl"
    if not os.path.exists(fn): continue
    raw = pickle.load(open(fn, "rb")); F = raw.get("fut")
    if F is None: continue
    t0 = K[s][i, 0] + 900
    d = feats(F[(F[:, 0] >= t0 - 86400) & (F[:, 0] < t0)]); h = feats(F[(F[:, 0] >= t0 - 3600) & (F[:, 0] < t0)])
    if not d: continue
    r = dict(g=g, s=s, t0=t0, **d)
    for k in ("flat_share", "flat_min", "single", "size_mode", "roundq"):
        if k in h: r[k + "_1h_vs_24h"] = h[k] - d[k]
    rows.append(r)
D = pd.DataFrame(rows); D.to_pickle("s3/botprint.pkl")
def auc(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float); a, b = a[np.isfinite(a)], b[np.isfinite(b)]
    if len(a) < 20 or len(b) < 20: return np.nan
    rk = st.rankdata(np.concatenate([a, b])); return (rk[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))
G = {g: D[D.g == g] for g in ("памп", "дамп", "покой")}
print(f"моментов: " + ", ".join(f"{g} {len(x)}" for g, x in G.items()))
print(f"{'признак':24s} медиана памп/дамп/покой | AUC памп-покой (1-я, 2-я пол.) | памп-дамп (1-я, 2-я пол.)")
for k in [c for c in D.columns if c not in ("g", "s", "t0")]:
    P, Dm, C = G["памп"], G["дамп"], G["покой"]
    h = lambda x, j: x[(x.t0 < MID) == (j == 0)][k]
    print(f"{k:24s} {P[k].median():.4f}/{Dm[k].median():.4f}/{C[k].median():.4f} | {auc(P[k], C[k]):.2f} ({auc(h(P, 0), h(C, 0)):.2f}, {auc(h(P, 1), h(C, 1)):.2f}) | "
          f"{auc(P[k], Dm[k]):.2f} ({auc(h(P, 0), h(Dm, 0)):.2f}, {auc(h(P, 1), h(Dm, 1)):.2f})")
