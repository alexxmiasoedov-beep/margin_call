import json, os, bisect, subprocess, glob
import numpy as np, pandas as pd
from scipy import stats
pd.set_option("display.width", 230); pd.set_option("display.max_columns", 40)

df = pd.read_csv("dataset.csv").sort_values("epoch").reset_index(drop=True)
sig = pd.read_csv("signals.csv")
HORIZ = {"r1h": 4, "r4h": 16, "r12h": 48, "r24h": 96}

# ---------- market proxy: median return across the whole 154-coin universe on a common 15m grid ----------
grid = np.arange((df.epoch.min() // 900 - 40) * 900, (df.epoch.max() // 900 + 110) * 900, 900)
closes = {}
for fn in glob.glob("klines/*.json"):
    s = os.path.basename(fn)[:-5]
    if s.startswith("_"): continue
    k = np.array(json.load(open(fn))["k"], dtype=float)
    ser = pd.Series(k[:, 4], index=k[:, 0].astype(int)).reindex(grid).ffill()
    closes[s] = ser.values
C = pd.DataFrame(closes, index=grid)
C = C.loc[:, C.std() / C.mean() > 0.002]   # drop stables
print("universe for market proxy:", C.shape[1], "coins")
MKT = {}
for name, n in HORIZ.items():
    fwd = (C.shift(-n) / C - 1) * 100
    MKT[name] = fwd.median(axis=1)   # per-bar median forward return of the universe

# BTC via gate (honours from/to)
t0, t1 = int(grid[0]), int(grid[-1])
j = []
a = t0
while a < t1:
    b = min(a + 900 * 990, t1)
    j += json.loads(subprocess.run(["curl", "-sS", f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair=BTC_USDT&interval=15m&from={a}&to={b}"], capture_output=True, text=True).stdout)
    a = b + 900
btc = pd.Series([float(k[2]) for k in j], index=[int(k[0]) for k in j]).reindex(grid).ffill()
print("BTC:", pd.to_datetime(btc.index[0], unit="s"), "→", pd.to_datetime(btc.index[-1], unit="s"), f"{(btc.iloc[-1]/btc.iloc[0]-1)*100:+.1f}%")
for name, n in HORIZ.items():
    MKT["btc_" + name] = (btc.shift(-n) / btc - 1) * 100

stable = [s for s in df.sym.unique() if s not in C.columns]
print("исключены (нет движения):", stable)
df = df[~df.sym.isin(stable)].copy()
df["bar"] = (df.epoch // 900) * 900
for name in HORIZ:
    df["m_" + name] = MKT[name].reindex(df.bar).values
    df["btc_" + name] = MKT["btc_" + name].reindex(df.bar).values
    df["x" + name] = df[name] - df["m_" + name]        # excess over universe median
    df["xb" + name] = df[name] - df["btc_" + name]     # excess over BTC
print("\nРынок (медиана альтов) за период по дням, %:")
_m = C.median(axis=1).dropna(); mk = pd.Series(_m.values / _m.values[0] * 100, index=pd.to_datetime(_m.index, unit="s")).resample("1D").last().pct_change() * 100
print(mk.round(2).to_string())

# ---------- CHNG meaning ----------
sig = sig.sort_values(["sym", "epoch"]).reset_index(drop=True)
sig["bar"] = (sig.epoch // 900) * 900
b24 = (C / C.shift(96) - 1) * 100
b4 = (C / C.shift(16) - 1) * 100
b1 = (C / C.shift(4) - 1) * 100
def lookup(M, r):
    return M[r.sym].get(r.bar, np.nan) if r.sym in M.columns else np.nan
sig["b24h"] = [lookup(b24, r) for r in sig.itertuples()]
sig["b4h"] = [lookup(b4, r) for r in sig.itertuples()]
sig["b1h"] = [lookup(b1, r) for r in sig.itertuples()]
sig["dbor"] = sig.groupby("sym").bor.diff()
sig["dbor_pct"] = sig.groupby("sym").bor.pct_change() * 100
print("\n== CHNG: Spearman с движением цены назад ==")
for c in ["b1h", "b4h", "b24h", "dbor", "dbor_pct"]:
    m = sig[[c, "chng"]].replace([np.inf, -np.inf], np.nan).dropna()
    print(f"  chng vs {c:8s}: rho={stats.spearmanr(m[c], m.chng)[0]:+.3f}")
nz = sig[sig.chng != 0]
print(f"  доля chng==0: {(sig.chng==0).mean()*100:.0f}%; среди ненулевых: min {nz.chng.min()}, max {nz.chng.max()}")
print("  Серия AUCTION 30.08 (chng, bor, rep, br, цена):")
a = sig[(sig.sym == "AUCTION") & (sig.ts >= "2026-08-30T04:30") & (sig.ts <= "2026-08-30T07:00")]
a = a.assign(px=[C["AUCTION"].get(b, np.nan) for b in a.bar])
print(a[["ts", "bor", "rep", "br", "chng", "px"]].to_string(index=False))
print("  Серия TUT 29.08 13:00-14:30:")
a = sig[(sig.sym == "TUT") & (sig.ts >= "2026-08-29T13:00") & (sig.ts <= "2026-08-29T14:30")]
a = a.assign(px=[C["TUT"].get(b, np.nan) for b in a.bar])
print(a[["ts", "bor", "rep", "br", "chng", "px"]].to_string(index=False))

# ---------- robustness of main candidates ----------
def report(d, label, cols=("r1h", "r4h", "r24h", "xr1h", "xr4h", "xr24h")):
    out = f"  {label:40s} n={len(d):5d} "
    for c in cols:
        x = d[c].dropna()
        if len(x) < 10: out += f"| {c} n/a "; continue
        p = stats.ttest_1samp(x, 0).pvalue
        out += f"| {c} {x.mean():+.2f}%/{(x>0).mean()*100:.0f}%{'*' if p<0.05 else ' '}"
    print(out)

print("\n== Все строки: сырые и сверх медианы рынка альтов (x) ==")
report(df, "baseline")
df["n4h_q"] = pd.cut(df.n4h, [-1, 5, 20, 35, 48, 1000])
print("\n-- по числу появлений монеты за последние 4ч (n4h) --")
g = df.groupby("n4h_q", observed=True)
print(g.agg(n=("xr4h", "size"), ncoins=("sym", "nunique"), r4h=("r4h", "mean"), xr4h=("xr4h", "mean"), xr24h=("xr24h", "mean"),
            xw24=("xr24h", lambda x: (x > 0).mean() * 100), med24=("xr24h", "median")).round(2).to_string())
df["br_q"] = pd.qcut(df.br, 5, duplicates="drop")
print("\n-- по B/R (квинтили), сверх рынка --")
g = df.groupby("br_q", observed=True)
print(g.agg(n=("xr4h", "size"), ncoins=("sym", "nunique"), xr1h=("xr1h", "mean"), xr4h=("xr4h", "mean"), xr24h=("xr24h", "mean"),
            xw24=("xr24h", lambda x: (x > 0).mean() * 100), med24=("xr24h", "median")).round(2).to_string())
df["rep_q"] = pd.qcut(df.lrep, 5, duplicates="drop")
print("\n-- по объёму погашений REP (квинтили), сверх рынка --")
g = df.groupby("rep_q", observed=True)
print(g.agg(n=("xr4h", "size"), ncoins=("sym", "nunique"), xr1h=("xr1h", "mean"), xr4h=("xr4h", "mean"), xr24h=("xr24h", "mean"),
            xw24=("xr24h", lambda x: (x > 0).mean() * 100)).round(2).to_string())
df["b4h_q"] = pd.qcut(df.b4h, 5, duplicates="drop")
print("\n-- по движению цены за 4ч ДО поста (квинтили), сверх рынка --")
g = df.groupby("b4h_q", observed=True)
print(g.agg(n=("xr4h", "size"), ncoins=("sym", "nunique"), xr1h=("xr1h", "mean"), xr4h=("xr4h", "mean"), xr24h=("xr24h", "mean"),
            xw24=("xr24h", lambda x: (x > 0).mean() * 100)).round(2).to_string())

# per-coin consistency: within each coin, is xr24h lower when n4h is high (above the coin's median)?
print("\n== Устойчивость по монетам (монеты с >=40 строками): знак разницы xr24h при высоком vs низком признаке ==")
for feat in ["n4h", "br", "lrep", "b4h"]:
    diffs = []
    for s, g in df.groupby("sym"):
        if len(g) < 40: continue
        med = g[feat].median()
        hi, lo = g[g[feat] > med].xr24h, g[g[feat] <= med].xr24h
        if len(hi) >= 10 and len(lo) >= 10:
            diffs.append(hi.mean() - lo.mean())
    diffs = np.array(diffs)
    p = stats.wilcoxon(diffs).pvalue if len(diffs) > 5 else np.nan
    print(f"  {feat:5s}: монет={len(diffs):3d}, у {np.mean(diffs<0)*100:.0f}% при высоком {feat} доходность ниже; медиана разницы {np.median(diffs):+.2f}%  (wilcoxon p={p:.3f})")

# per-day consistency of baseline
df["day"] = pd.to_datetime(df.epoch, unit="s").dt.date
print("\n== По дням: средняя xr24h всех строк и доля положительных ==")
print(df.groupby("day").agg(n=("xr24h", "size"), r24h=("r24h", "mean"), m24=("m_r24h", "mean"), xr24h=("xr24h", "mean"), xw=("xr24h", lambda x: (x > 0).mean() * 100)).round(2).to_string())

# time split: fit rule on first half, test on second half
mid = df.epoch.median()
A, B = df[df.epoch < mid], df[df.epoch >= mid]
print("\n== Проверка на второй половине недели (правила, найденные на первой) ==")
for label, mask_fn in [
    ("n4h >= 36 (висит почти каждый пост 4ч)", lambda d: d.n4h >= 36),
    ("n4h <= 5 (свежая)", lambda d: d.n4h <= 5),
    ("br > 20", lambda d: d.br > 20),
    ("br < 4", lambda d: d.br < 4),
    ("b4h > +3% до поста", lambda d: d.b4h > 3),
    ("b4h < -3% до поста", lambda d: d.b4h < -3),
    ("n4h>=36 & b4h>+3%", lambda d: (d.n4h >= 36) & (d.b4h > 3)),
    ("n4h>=36 & br>20", lambda d: (d.n4h >= 36) & (d.br > 20)),
    ("REP верхний квинтиль", lambda d: d.lrep > df.lrep.quantile(.8)),
]:
    for nm, part in (("1-я половина", A), (" 2-я половина", B)):
        report(part[mask_fn(part)], f"{label} [{nm}]", cols=("xr1h", "xr4h", "xr24h"))

# ---------- dynamics inside a run: does BOR growth / REP growth between consecutive posts predict? ----------
df = df.sort_values(["sym", "epoch"])
df["dbor_pct"] = df.groupby("sym").bor.pct_change() * 100
df["drep_pct"] = df.groupby("sym").rep.pct_change() * 100
df["gap_prev"] = df.groupby("sym").epoch.diff()
w = df[(df.gap_prev <= 1800)].replace([np.inf, -np.inf], np.nan)
print("\n== Внутри серии: изменение BOR / REP относительно предыдущего поста (<=30 мин назад) ==")
report(w[w.dbor_pct > 5], "BOR вырос >5% за пост", cols=("xr1h", "xr4h", "xr24h"))
report(w[w.dbor_pct < -5], "BOR упал >5% за пост", cols=("xr1h", "xr4h", "xr24h"))
report(w[w.drep_pct > 10], "REP вырос >10% за пост (гасят займы)", cols=("xr1h", "xr4h", "xr24h"))
report(w[(w.drep_pct > 10) & (w.dbor_pct.abs() < 1)], "REP растёт, BOR стоит", cols=("xr1h", "xr4h", "xr24h"))
report(w[(w.dbor_pct > 5) & (w.drep_pct.abs() < 1)], "BOR растёт, REP стоит", cols=("xr1h", "xr4h", "xr24h"))
df.to_csv("dataset3.csv", index=False)
