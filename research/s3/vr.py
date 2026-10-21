"""«Характер случайности» монеты: variance ratio VR(4) и VR(16) 15-мин доходностей за 7 суток ДО начала движения.
События: движение за 4 ч ≥ 5% (вверх или вниз), первое за сутки. Исход: доходность следующих 24 ч в сторону движения
(плюс — продолжение, минус — откат), по корзинам VR, по годам."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb"))
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
def roll(x, w):
    cs = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)]); out = np.full(len(x), np.nan); out[w - 1:] = cs[w:] - cs[:-w]; return out
rows = []
for s, a in K.items():
    c = a["c"].astype(np.float64); qv = a["qv"].astype(np.float64); n = len(c)
    if n < 2000: continue
    r = np.zeros(n); r[1:] = np.diff(np.log(c))
    W = 672; s1, s2 = roll(r, W), roll(r * r, W); var1 = (s2 - s1 ** 2 / W) / (W - 1)
    r4 = np.zeros(n); r4[4:] = np.log(c[4:] / c[:-4]); q1, q2 = roll(r4, W - 3), roll(r4 * r4, W - 3); var4 = (q2 - q1 ** 2 / (W - 3)) / (W - 4)
    r16 = np.zeros(n); r16[16:] = np.log(c[16:] / c[:-16]); p1, p2 = roll(r16, W - 15), roll(r16 * r16, W - 15); var16 = (p2 - p1 ** 2 / (W - 15)) / (W - 16)
    vr4, vr16 = var4 / (4 * var1), var16 / (16 * var1)
    mv = np.full(n, np.nan); mv[16:] = c[16:] / c[:-16] - 1
    v24 = roll(qv, 96); last = -10**9
    for j in np.flatnonzero(np.abs(np.nan_to_num(mv)) >= 0.05):
        if j < W + 40 or j + 97 >= n or j - last < 96 or v24[j] < 3e6: continue
        last = j; jb = j - 16                                              # VR — по неделе, закончившейся до начала движения
        d = np.sign(mv[j]); f = c[j + 96] / c[j] - 1
        rows.append((s, a["t"][j] + 900, d, mv[j], vr4[jb], vr16[jb], d * f, d * (c[j + 16] / c[j] - 1)))
D = pd.DataFrame(rows, columns=["s", "t", "dir", "move", "vr4", "vr16", "cont24", "cont4"])
D["year"] = np.where(D.t < CUT, "1-й год", "2-й год"); D.to_pickle("s3/vr.pkl")
print(f"движений ≥ 5% за 4 ч: {len(D)} (вверх {(D.dir > 0).sum()}, вниз {(D.dir < 0).sum()}); продолжение за 24 ч в среднем {D.cont24.mean() * 100:+.2f}%")
for k in ("vr4", "vr16"):
    for dname, dm in (("вверх", D.dir > 0), ("вниз", D.dir < 0)):
        x = D[dm]; q = pd.qcut(x[k], 5, duplicates="drop"); line = f"{k} {dname:5s} |"
        for b, g in x.groupby(q, observed=True):
            y = g.groupby("year").cont24.mean() * 100
            line += f" ≤{b.right:.2f}: {g.cont24.mean() * 100:+.2f} ({y.get('1-й год', np.nan):+.2f}/{y.get('2-й год', np.nan):+.2f})"
        print(line)
