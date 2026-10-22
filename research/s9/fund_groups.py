"""Агрегированный фандинг Binance (логика ботов 4MulaT | Funding): в каждые 00/08/16 UTC — последняя выплаченная ставка каждой монеты
(в пересчёте на 8 ч), доли групп HIGH (> 0,01%), STANDARD (≈ 0,01%), LOW (0…0,01%), NEGATIVE (< 0) и MID (средняя).
Будущий доход равновзвешенного индекса альтов (медиана по монетам) и BTC за 1 / 3 / 7 суток."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
T0 = datetime.datetime(2024, 11, 1, tzinfo=datetime.timezone.utc).timestamp(); T1 = datetime.datetime(2026, 9, 30, tzinfo=datetime.timezone.utc).timestamp()
grid = np.arange(T0, T1, 8 * 3600)
rates = np.full((len(grid), len(F)), np.nan); names = list(F)
for k, s in enumerate(names):
    f = F[s]
    if len(f) < 10: continue
    idx = np.searchsorted(f[:, 0], grid, "right") - 1; ok = idx >= 0
    r = np.full(len(grid), np.nan); r[ok] = f[idx[ok], 2] * 8 / np.maximum(f[idx[ok], 1], 1)
    stale = np.zeros(len(grid), bool); stale[ok] = grid[ok] - f[idx[ok], 0] > 2 * 86400; r[stale] = np.nan
    rates[:, k] = r
n = np.isfinite(rates).sum(1)
H = pd.DataFrame(dict(t=grid, n=n, high=np.nansum(rates > 0.000101, 1) / n, std=np.nansum((rates >= 0.000099) & (rates <= 0.000101), 1) / n,
                      low=np.nansum((rates >= 0) & (rates < 0.000099), 1) / n, neg=np.nansum(rates < 0, 1) / n, mid=np.nanmean(rates, 1),
                      med=np.nanmedian(rates, 1)))
# индекс альтов: медиана доходностей монет (кроме BTC, ETH) за 1/3/7 суток от момента
def fwd(hours):
    out = np.full(len(grid), np.nan); btc = np.full(len(grid), np.nan)
    rets = []
    for s, a in K.items():
        t = a["t"] + 900; c = a["c"].astype(np.float64)
        i0 = np.searchsorted(t, grid); i1 = np.searchsorted(t, grid + hours * 3600)
        ok = (i0 < len(t)) & (i1 < len(t)) & (np.abs(t[np.minimum(i0, len(t) - 1)] - grid) < 1800)
        r = np.full(len(grid), np.nan); r[ok] = c[i1[ok]] / c[i0[ok]] - 1
        if s == "BTC": btc = r
        elif s != "ETH": rets.append(r)
    R = np.vstack(rets); return np.nanmedian(R, 0), btc
for h in (24, 72, 168):
    H[f"alt{h}"], H[f"btc{h}"] = fwd(h)
H["half"] = np.where(H.t < datetime.datetime(2025, 10, 15, tzinfo=datetime.timezone.utc).timestamp(), 1, 2)
H.to_pickle("s9/fund_groups.pkl")
print(H[["high", "std", "low", "neg", "mid"]].describe().round(4).to_string())
for col in ("high", "neg", "mid"):
    H["b"] = pd.qcut(H[col], 5, labels=False, duplicates="drop")
    g = H.groupby("b").agg(lo=(col, "min"), hi=(col, "max"), n=("t", "size"), alt24=("alt24", "mean"), alt72=("alt72", "mean"), alt168=("alt168", "mean"),
                           btc72=("btc72", "mean"))
    g2 = H.groupby(["b", "half"]).alt72.mean().unstack()
    g["alt72_h1"], g["alt72_h2"] = g2[1], g2[2]
    print(f"=== по квинтилям {col}"); print((g * [1, 1, 1, 100, 100, 100, 100, 100, 100]).round(3).to_string())
