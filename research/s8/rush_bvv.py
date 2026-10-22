"""Всплеск доли Bitvavo (× к обычной за сутки) в момент турецкого набега (сделки журнала 🇹🇷 из бэктеста rush_wb.py)."""
import json, os, re, pickle, datetime
import numpy as np, pandas as pd
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
K = pickle.load(open("s2/k2y.pkl", "rb")); A = pickle.load(open("s8/rush_wb.pkl", "rb"))["A"].copy()
fx = np.load("s8/eurusd.npy"); r = lambda ts: np.interp(ts, fx[:, 0], fx[:, 1])
CUT = datetime.datetime(2025, 10, 1, tzinfo=datetime.timezone.utc).timestamp()
rows = []
for x in A.itertuples():
    c = strip(x.s); fn = f"s8/bvr/{c}_{int(x.t)}.json"; d = None
    if os.path.exists(fn):
        j = json.load(open(fn))
        if isinstance(j, list) and j: d = {int(y[0]) // 1000: float(y[5]) * float(y[4]) * r(int(y[0]) // 1000) for y in j}
    if not d or min(d) > x.t - 24 * 3600: rows.append((np.nan, np.nan, np.nan)); continue
    a = K[x.s]; t = a["t"]; jj = x.j; qv = a["qv"].astype(np.float64)
    v = np.array([d.get(int(t[k]), 0.0) for k in range(jj - 95, jj + 1)]); f = qv[jj - 95:jj + 1]
    hv = v.reshape(24, 4).sum(1); hf = f.reshape(24, 4).sum(1); sh = hv / np.maximum(hv + hf, 1)
    rows.append((sh[-1], np.median(sh[:-1]), sh[-1] / max(np.median(sh[:-1]), 1e-4)))
A[["bsh", "bnorm", "bx"]] = rows; A["y"] = np.where(A.t < CUT, 1, 2)
def st(nm, g):
    y1, y2 = g[g.y == 1], g[g.y == 2]; qm = g.groupby("q").p.mean()
    print(f"  {nm:26s} {len(g):4d} WR {(g.p > 0).mean():.1%} {g.p.mean() * 100:+.2f}% (1-й {len(y1)} {(y1.p > 0).mean():.0%} {y1.p.mean() * 100:+.2f}, "
          f"2-й {len(y2)} {(y2.p > 0).mean():.0%} {y2.p.mean() * 100:+.2f}) итог {g.p.sum() * 10:+.1f} USDT, кв. {(qm > 0).sum()}/{len(qm)}")
print("турецкий набег (тейк 10 / стоп 15 / 24 ч), по всплеску доли Bitvavo в момент сигнала:")
st("все", A); st("нет пары на Bitvavo", A[A.bx.isna()])
for lo, hi in ((0, 1), (1, 2), (2, 4), (4, 8), (8, 1e9)):
    st(f"× {lo:g}–{hi:g}", A[(A.bx >= lo) & (A.bx < hi)])
for k in (2, 3, 4):
    st(f"× ≥ {k}", A[A.bx >= k]); st(f"× < {k} или нет пары", A[~(A.bx >= k)])
print("доля Bitvavo за час, медиана:", f"{A.bsh.median():.2%}", "обычная:", f"{A.bnorm.median():.2%}")
q = A[A.bx >= 4].groupby("q").p.agg(["size", "mean"]).join(A[~(A.bx >= 4)].groupby("q").p.agg(["size", "mean"]), lsuffix="_всплеск", rsuffix="_остальные")
print(q.round(4).to_string())
A.to_pickle("s8/rush_bvv.pkl")
