"""«Пробуждение спящей монеты»: на закрытии 15-мин свечи объём за сутки ≥ X× средней дневной за предыдущие 6 суток, цена за сутки
выросла на lo…hi, объём суток ≥ Vmin $ → шорт в закрытии. Одна сделка на монету за 48 ч. Комиссия 0,1%, фандинг по факту."""
import pickle, datetime, re, glob, os, sys
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
UTC = datetime.timezone.utc
T0 = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); T1 = datetime.datetime(2026, 10, 15, tzinfo=UTC).timestamp()
def roll(x, w):
    cs = np.concatenate([[0.0], np.cumsum(x, dtype=np.float64)]); out = np.full(len(x), np.nan); out[w - 1:] = cs[w:] - cs[:-w]; return out
PRE = {}
for s, a in K.items():
    qv = a["qv"].astype(np.float64); c = a["c"].astype(np.float64); n = len(qv)
    if n < 800: continue
    q24 = roll(qv, 96); qp = np.full(n, np.nan); qp[96:] = roll(qv, 576)[:-96]          # 6 суток до последних суток
    r24 = np.full(n, np.nan); r24[96:] = c[96:] / c[:-96] - 1
    PRE[s] = (q24, qp / 6, r24)
def events(X, lo, hi, vmin=3e6, gap=192):
    out = []
    for s, (q24, qd, r24) in PRE.items():
        t = K[s]["t"]; te = t + 900
        ok = (q24 >= X * np.maximum(qd, 1)) & (q24 >= vmin) & (r24 > lo) & (r24 <= hi) & (te >= T0) & (te <= T1) & (qd > 0)
        last = -10**9
        for j in np.flatnonzero(ok):
            if j - last >= gap: out.append((s, int(j))); last = j
    return out
def trade(s, j, tp, sl, hold):
    a = K[s]; t = a["t"]; e = float(a["c"][j]); end = min(j + hold, len(t) - 1)
    hi = a["h"][j + 1:end + 1].astype(np.float64); lo = a["l"][j + 1:end + 1].astype(np.float64)
    bad, good = np.flatnonzero(hi >= e * (1 + sl)), np.flatnonzero(lo <= e * (1 - tp))
    q1 = bad[0] if len(bad) else 10**9; q2 = good[0] if len(good) else 10**9
    if q1 <= q2 and q1 < 10**9: q = j + 1 + q1; px = -sl; how = "стоп"
    elif q2 < 10**9: q = j + 1 + q2; px = tp; how = "тейк"
    else: q = end; px = 1 - float(a["c"][end]) / e; how = "время"
    fr = F.get(s); t_in = t[j] + 900; t_out = t[q] + 900; fund = 0.0
    if fr is not None:
        m = (fr[:, 0] > t_in) & (fr[:, 0] <= t_out); fund = float(fr[m, 2].sum())
    return t_in, px + fund - 0.001, fund, how
def table(ev, tp, sl, hold):
    rows = [(s, *trade(s, j, tp, sl, hold)) for s, j in ev]
    d = pd.DataFrame(rows, columns=["s", "t", "p", "fund", "how"]); d["q"] = pd.to_datetime(d.t, unit="s").dt.to_period("Q").astype(str)
    return d
if __name__ == "__main__":
    res = []
    for X in (10, 20, 30, 50):
        for lo, hi in ((0.05, 0.15), (0.1, 0.3), (0.15, 0.4), (0.3, 1.0)):
            ev = events(X, lo, hi)
            if len(ev) < 30: continue
            d = table(ev, 0.1, 0.15, 96); qm = d.groupby("q").p.mean()
            res.append((X, f"{lo:.0%}–{hi:.0%}", len(d), d.s.nunique(), round(d.p.mean() * 100, 2), round((d.p > 0).mean() * 100), round(d.fund.mean() * 100, 2),
                        f"{(qm > 0).sum()}/{len(qm)}", " ".join(f"{k[2:]}:{v * 100:+.1f}" for k, v in qm.items())))
    pd.set_option("display.width", 300)
    print(pd.DataFrame(res, columns=["объём ×", "рост за сутки", "сделок", "монет", "итог %", "в плюсе %", "фандинг %", "кварталов в плюсе", "по кварталам"]).to_string(index=False))
