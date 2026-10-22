"""Турецкий набег (🇹🇷) с долей лиры Binance + WhiteBIT: те же пороги (доля за час ≥ 10%, ≥ 3× обычной за 7 сут, рост за 4 ч ≥ 10%,
объём ≥ 200 тыс. $), тейк 10 / стоп 15 / 24 ч, одна сделка на монету за 48 ч. Сравнение с долей только Binance."""
import pickle, datetime, os, re
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as sw
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
X = pickle.load(open("s2/fiat_TRY.pkl", "rb")); pairs, Dz = X["pairs"], X["D"]; fx = Dz["USDTTRY"]
UTC = datetime.timezone.utc
T0 = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); T1 = datetime.datetime(2026, 10, 15, tzinfo=UTC).timestamp()
CUT = datetime.datetime(2025, 10, 1, tzinfo=UTC).timestamp()
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
def roll(x, w):
    cs = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)]); out = np.full(len(x), np.nan); out[w - 1:] = cs[w:] - cs[:-w]; return out
def align(t, b):
    """объём в $ по 15-мин свечам фьючерса (t — время открытия), b — [t, close, объём в лирах]"""
    n = len(t); v = np.zeros(n)
    if b is None or not len(b): return v, np.inf
    idx = np.searchsorted(t, b[:, 0]); ok = idx < n; ok[ok] &= t[idx[ok]] == b[ok, 0]
    v[idx[ok]] = b[ok, 2] / np.interp(b[ok, 0], fx[:, 0], fx[:, 1])
    nz = b[b[:, 2] > 0]; return v, (nz[0, 0] if len(nz) else np.inf)
def prep(s, tvb, fb, tvw, fw, use_b, use_w):
    a = K[s]; t = a["t"]; n = len(t)
    tv = (tvb if use_b else 0) + (tvw if use_w else 0)
    first = min(fb if use_b else np.inf, fw if use_w else np.inf)
    fq = a["qv"].astype(np.float64); c = a["c"].astype(np.float64)
    t1 = roll(tv, 4); f1 = roll(fq, 4); sh = t1 / np.maximum(t1 + f1, 1)
    med = np.full(n, np.nan)
    if n > 700:
        hourly = sh[3::4]; m = np.full(len(hourly), np.nan); m[168:] = np.median(sw(hourly[:-1], 168)[:len(hourly) - 168], axis=1)
        med[3::4] = m; med = pd.Series(med).ffill().values
    r4 = np.full(n, np.nan); r4[16:] = c[16:] / c[:-16] - 1
    return sh, med, r4, f1 + t1, first
def trade(s, j, tp, sl, hold):
    a = K[s]; t = a["t"]; e = float(a["c"][j]); end = min(j + hold, len(t) - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64); lo = a["l"][j + 1:end + 1].astype(np.float64)
    bad, good = np.flatnonzero(hi >= e * (1 + sl)), np.flatnonzero(lo <= e * (1 - tp))
    q1 = bad[0] if len(bad) else 10**9; q2 = good[0] if len(good) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; px = -sl
    elif q2 < 10**9: q = j + 1 + q2; px = tp
    else: q = end; px = 1 - float(a["c"][end]) / e
    fr = F.get(s); t_in = t[j] + 900; t_out = t[q] + 900; fund = 0.0
    if fr is not None:
        m = (fr[:, 0] > t_in) & (fr[:, 0] <= t_out); fund = float(fr[m, 2].sum())
    return t_in, px + fund - 0.001, fund
def events(PRE, S=0.10, M=3.0, lo=0.10, hi=1.0, vmin=200e3, gap=192):
    out = []
    for s, (sh, med, r4, v1, first) in PRE.items():
        te = K[s]["t"] + 900
        ok = (sh >= S) & (sh >= M * np.maximum(med, 1e-4)) & (r4 > lo) & (r4 <= hi) & (v1 >= vmin) & (te >= T0) & (te <= T1) & (te > first + 8 * 86400)
        last = -10**9
        for j in np.flatnonzero(ok):
            if j - last >= gap: out.append((s, int(j))); last = j
    return out
WB = {f[:-4]: np.load(f"s8/wb/{f}") for f in os.listdir("s8/wb") if f.endswith(".npy") and f != "USDT.npy"}
V = {}
for s in K:
    name = pairs.get(s); c = strip(s)
    b = Dz.get(f"{name}TRY") if name else None
    w = WB.get(c if c in WB else s)
    if b is None and w is None: continue
    t = K[s]["t"]; vb, fb = align(t, b); vw, fw = align(t, w); V[s] = (vb, fb, vw, fw, b is not None, w is not None)
print("монет с парой к лире: Binance", sum(x[4] for x in V.values()), "WhiteBIT", sum(x[5] for x in V.values()), "обе", sum(x[4] and x[5] for x in V.values()))
def run(nm, use_b, use_w, only_b=False, **kw):
    PRE = {s: prep(s, vb, fb, vw, fw, use_b, use_w) for s, (vb, fb, vw, fw, hb, hw) in V.items() if (hb or not only_b) and ((use_b and hb) or (use_w and hw))}
    ev = events(PRE, **kw)
    d = pd.DataFrame([(s, j, *trade(s, j, 0.1, 0.15, 96)) for s, j in ev], columns=["s", "j", "t", "p", "fund"])
    d["q"] = pd.to_datetime(d.t, unit="s").dt.to_period("Q").astype(str); qm = d.groupby("q").p.mean(); y1 = d[d.t < CUT]; y2 = d[d.t >= CUT]
    print(f"{nm:52s} {len(d):5d} сделок, {d.s.nunique():3d} монет, WR {(d.p > 0).mean():.1%}, {d.p.mean() * 100:+.2f}% "
          f"(1-й {len(y1)} {y1.p.mean() * 100:+.2f}, 2-й {len(y2)} {y2.p.mean() * 100:+.2f}), итог {d.p.sum() * 10:+.1f} USDT, кв. {(qm > 0).sum()}/{len(qm)} | "
          + " ".join(f"{k[2:]}:{v * 100:+.1f}" for k, v in qm.items()), flush=True)
    return d
if __name__ == "__main__":
    A = run("только Binance (как сейчас)", True, False)
    B = run("Binance + WhiteBIT, монеты с парой на Binance", True, True, only_b=True)
    C = run("Binance + WhiteBIT, все монеты", True, True)
    W = run("только WhiteBIT", False, True)
    for S in (0.12, 0.15):
        run(f"Binance + WhiteBIT, все монеты, доля ≥ {S:.0%}", True, True, S=S)
    ka = set(zip(A.s, A.j)); kc = set(zip(C.s, C.j))
    new = C[[k not in ka for k in zip(C.s, C.j)]]; lost = A[[k not in kc for k in zip(A.s, A.j)]]; both = C[[k in ka for k in zip(C.s, C.j)]]
    for nm, g in (("общие сделки", both), ("новые с WhiteBIT", new), ("пропали", lost)):
        y1 = g[g.t < CUT]; y2 = g[g.t >= CUT]
        print(f"  {nm:20s} {len(g):5d}, WR {(g.p > 0).mean():.1%}, {g.p.mean() * 100:+.2f}% (1-й {len(y1)} {y1.p.mean() * 100:+.2f}, 2-й {len(y2)} {y2.p.mean() * 100:+.2f})")
    pickle.dump(dict(A=A, B=B, C=C, W=W), open("s8/rush_wb.pkl", "wb"))
