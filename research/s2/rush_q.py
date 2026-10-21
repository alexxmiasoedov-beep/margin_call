"""«Набег розницы» (турецкая лира на споте Binance): на закрытии 15-мин свечи доля пары к TRY в объёме за час (TRY-спот + фьючерс)
≥ S и в M раз выше её обычной доли (медиана за 7 суток), цена за 4 ч изменилась на lo…hi → шорт в закрытии.
Одна сделка на монету за 48 ч, комиссия 0,1%, фандинг по факту."""
import pickle, datetime, sys
import numpy as np, pandas as pd
from numpy.lib.stride_tricks import sliding_window_view as sw
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
import os; Q = os.environ.get("Q", "TRY"); X = pickle.load(open(f"s2/fiat_{Q}.pkl", "rb")); pairs, D = X["pairs"], X["D"]; fx = D[f"USDT{Q}"]
UTC = datetime.timezone.utc
T0 = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); T1 = datetime.datetime(2026, 10, 15, tzinfo=UTC).timestamp()
def roll(x, w):
    cs = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)]); out = np.full(len(x), np.nan); out[w - 1:] = cs[w:] - cs[:-w]; return out
PRE = {}
for s, name in pairs.items():
    a = K.get(s); b = D.get(f"{name}{Q}")
    if a is None or b is None: continue
    t = a["t"]; n = len(t); tv = np.zeros(n)
    idx = np.searchsorted(t, b[:, 0]); ok = idx < n; ok[ok] &= t[idx[ok]] == b[ok, 0]
    tv[idx[ok]] = b[ok, 2] / np.interp(b[ok, 0], fx[:, 0], fx[:, 1])
    fq = a["qv"].astype(np.float64); c = a["c"].astype(np.float64)
    t1 = roll(tv, 4); f1 = roll(fq, 4); sh = t1 / np.maximum(t1 + f1, 1)
    med = np.full(n, np.nan)
    if n > 700:
        hourly = sh[3::4]; m = np.full(len(hourly), np.nan); m[168:] = np.median(sw(hourly[:-1], 168)[:len(hourly) - 168], axis=1)   # медиана долей за 7 сут до этого часа
        med[3::4] = m
        med = pd.Series(med).ffill().values
    r4 = np.full(n, np.nan); r4[16:] = c[16:] / c[:-16] - 1
    PRE[s] = (sh, med, r4, f1 + t1, b[0, 0])
def events(S, M, lo, hi, vmin=200e3, gap=192):
    out = []
    for s, (sh, med, r4, v1, first) in PRE.items():
        te = K[s]["t"] + 900
        ok = (sh >= S) & (sh >= M * np.maximum(med, 1e-4)) & (r4 > lo) & (r4 <= hi) & (v1 >= vmin) & (te >= T0) & (te <= T1) & (te > first + 8 * 86400)
        last = -10**9
        for j in np.flatnonzero(ok):
            if j - last >= gap: out.append((s, int(j))); last = j
    return out
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
if __name__ == "__main__":
    res = []
    for S, M in ((0.05, 3), (0.1, 3), (0.1, 5), (0.2, 3), (0.2, 5)):
        for lo, hi in ((-0.03, 0.03), (0.03, 0.1), (0.1, 1.0), (-1, -0.03)):
            ev = events(S, M, lo, hi)
            if len(ev) < 30: continue
            d = pd.DataFrame([(s, *trade(s, j, 0.1, 0.15, 96)) for s, j in ev], columns=["s", "t", "p", "fund"])
            d["q"] = pd.to_datetime(d.t, unit="s").dt.to_period("Q").astype(str); qm = d.groupby("q").p.mean()
            res.append((S, M, f"{lo:+.0%}…{hi:+.0%}", len(d), d.s.nunique(), round(d.p.mean() * 100, 2), round((d.p > 0).mean() * 100), round(d.fund.mean() * 100, 2),
                        f"{(qm > 0).sum()}/{len(qm)}", " ".join(f"{k[2:]}:{v * 100:+.1f}" for k, v in qm.items())))
    pd.set_option("display.width", 300)
    print(pd.DataFrame(res, columns=["доля ≥", "× к норме", "цена за 4 ч", "сделок", "монет", "итог %", "в плюсе %", "фанд %", "кв.+", "по кварталам"]).to_string(index=False))
