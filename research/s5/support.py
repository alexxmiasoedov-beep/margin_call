"""«Кто-то держит цену»: как монета ведёт себя на падениях рынка за 3 суток до момента (доля падений рынка, которую она
повторяет, бета, корреляция). Гипотеза: монету, которая не падает вместе с рынком, поддерживает крупный покупатель
(накопление перед разгоном). Исход — доходность к рынку за 24/72 ч и памп +15% в следующие 24 ч; по годам."""
import pickle, datetime
import numpy as np, pandas as pd
T = np.load("s4/T.npy"); C = np.load("s4/G_c.npy").astype(np.float64); Hh = np.load("s4/G_h.npy"); Q = np.load("s4/G_qv.npy")
n, m = C.shape
R = np.full_like(C, np.nan); R[1:] = C[1:] / C[:-1] - 1; R[np.abs(R) > 0.5] = np.nan
cnt = np.sum(~np.isnan(R), axis=1); mk = np.where(cnt >= 50, np.nanmedian(R, axis=1), np.nan)        # рынок — медиана монет
UTC = datetime.timezone.utc; A = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
W = 288; THR = -0.004
def csum(x):
    x = np.where(np.isnan(x), 0.0, x); return np.concatenate([np.zeros((1,) + x.shape[1:]), np.cumsum(x, axis=0)])
mkz = np.where(np.isnan(mk), 0.0, mk)
down = (mkz < THR).astype(np.float64)
ok = ~np.isnan(R)
S_cm = csum(R * mkz[:, None]); S_mm = csum(np.where(ok, mkz[:, None] ** 2, 0)); S_c = csum(R); S_m = csum(np.where(ok, mkz[:, None], 0))
S_cc = csum(R ** 2); S_n = csum(ok.astype(np.float64))
S_dc = csum(np.where(ok, R * down[:, None], 0)); S_dm = csum(np.where(ok, (mkz * down)[:, None], 0))
S_q = csum(Q.astype(np.float64))
rows = []
first = np.argmax(~np.isnan(C), axis=0)
mc = np.concatenate([[1.0], np.cumprod(1 + mkz)])          # индекс рынка
for i in range(max(np.searchsorted(T, A), W + 700), n - 289, 4):
    w = lambda S: S[i + 1] - S[i + 1 - W]
    nn = w(S_n); okc = (nn >= W * 0.9) & (first + 672 <= i) & ~np.isnan(C[i])
    v24 = S_q[i + 1] - S_q[i + 1 - 96]; okc &= v24 >= 3e6
    if not okc.any(): continue
    k = np.flatnonzero(okc)
    cm, mm, c1, m1, cc = w(S_cm)[k], w(S_mm)[k], w(S_c)[k], w(S_m)[k], w(S_cc)[k]; nk = nn[k]
    cov = cm / nk - c1 / nk * m1 / nk; vm = mm / nk - (m1 / nk) ** 2; vc = cc / nk - (c1 / nk) ** 2
    beta = cov / np.maximum(vm, 1e-12); corr = cov / np.sqrt(np.maximum(vm * vc, 1e-18))
    dm = w(S_dm)[k]; dcap = np.where(dm < -0.01, w(S_dc)[k] / np.minimum(dm, -1e-9), np.nan)
    r3 = C[i, k] / C[i - W, k] - 1; m3 = mc[i + 1] / mc[i + 1 - W] - 1
    f24 = C[i + 96, k] / C[i, k] - 1 - (mc[i + 97] / mc[i + 1] - 1); f72 = C[i + 288, k] / C[i, k] - 1 - (mc[i + 289] / mc[i + 1] - 1)
    hmax = np.nanmax(Hh[i + 1:i + 97, k], axis=0) / C[i, k] - 1
    for a in zip(k, beta, corr, dcap, r3 - m3, f24, f72, hmax, v24[k]):
        rows.append((T[i] + 900,) + a + (m3, dm[list(k).index(a[0])] if False else 0))
D = pd.DataFrame(rows, columns=["t", "k", "beta", "corr", "dcap", "rel3", "f24", "f72", "hmax", "v24", "m3", "_"]).drop(columns="_")
D["y"] = np.where(D.t < CUT, 1, 2); D.to_pickle("s5/support.pkl")
print(len(D), "наблюдений (монета × час)")
for col in ("dcap", "beta", "corr", "rel3"):
    q = pd.qcut(D[col].rank(method="first"), 5, labels=False); line = f"{col:5s}"
    for b in range(5):
        g = D[q == b]
        line += (f" | Q{b + 1} ≤{g[col].max():.2f}: 24ч {g[g.y == 1].f24.mean() * 100:+.2f}/{g[g.y == 2].f24.mean() * 100:+.2f}"
                 f" 72ч {g[g.y == 1].f72.mean() * 100:+.2f}/{g[g.y == 2].f72.mean() * 100:+.2f} памп {(g.hmax >= 0.15).mean():.1%}")
    print(line)
