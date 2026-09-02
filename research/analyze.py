import json, os, bisect
import numpy as np, pandas as pd
from scipy import stats

pd.set_option("display.width", 200); pd.set_option("display.max_columns", 30)
sig = pd.read_csv("signals.csv")
K = {}
for s in sig.sym.unique():
    fn = f"klines/{s}.json"
    if os.path.exists(fn):
        d = json.load(open(fn))
        k = np.array(d["k"], dtype=float)  # t, o, h, l, c, v
        K[s] = (k[:, 0].astype(int), k)
print("symbols with prices:", len(K), "of", sig.sym.nunique())

HORIZ = {"r15m": 1, "r1h": 4, "r4h": 16, "r12h": 48, "r24h": 96}
rows = []
for r in sig.itertuples():
    if r.sym not in K:
        continue
    t, k = K[r.sym]
    i = bisect.bisect_right(t, r.epoch) - 1   # bar containing the post
    if i < 4 or i + 96 >= len(t):
        continue
    if r.epoch - t[i] > 900 * 2:   # gap in data
        continue
    base = k[i + 1, 1]  # next bar open — no lookahead
    d = {"sym": r.sym, "epoch": r.epoch, "post": r.post, "bor": r.bor, "rep": r.rep, "br": r.br, "chng": r.chng, "rank": r.rank}
    for name, n in HORIZ.items():
        d[name] = (k[i + n, 4] / base - 1) * 100
    d["mfe24"] = (k[i + 1:i + 97, 2].max() / base - 1) * 100
    d["mae24"] = (k[i + 1:i + 97, 3].min() / base - 1) * 100
    d["b1h"] = (k[i, 4] / k[i - 4, 4] - 1) * 100       # backward 1h
    d["b4h"] = (k[i, 4] / k[i - 16, 4] - 1) * 100
    d["b15m"] = (k[i, 4] / k[i - 1, 4] - 1) * 100
    d["vol_ratio"] = k[i, 5] / (k[i - 16:i, 5].mean() + 1e-9)
    rows.append(d)
df = pd.DataFrame(rows)
df["lbor"] = np.log10(df.bor + 1); df["lrep"] = np.log10(df.rep + 1)
df["net"] = df.bor - df.rep; df["lnet"] = np.sign(df.net) * np.log10(df.net.abs() + 1)
df["chng_sign"] = np.sign(df.chng)
# repeats: how many times same symbol appeared in previous 24h / 4h
df = df.sort_values("epoch").reset_index(drop=True)
df["n24h"] = 0; df["n4h"] = 0; df["dbr"] = np.nan
for s, g in df.groupby("sym"):
    e = g.epoch.values
    n24 = [np.sum((e < e[j]) & (e >= e[j] - 86400)) for j in range(len(e))]
    n4 = [np.sum((e < e[j]) & (e >= e[j] - 14400)) for j in range(len(e))]
    df.loc[g.index, "n24h"] = n24; df.loc[g.index, "n4h"] = n4
    df.loc[g.index, "dbr"] = g.br.diff().values
df["first24"] = (df.n24h == 0).astype(int)
df.to_csv("dataset.csv", index=False)
print("rows:", len(df), "period:", pd.to_datetime(df.epoch.min(), unit="s"), "→", pd.to_datetime(df.epoch.max(), unit="s"))

# what is CHNG?  correlate with backward/forward returns
print("\n== Что такое CHNG (Spearman с движением цены до/после поста) ==")
for c in ["b15m", "b1h", "b4h", "r15m", "r1h", "r4h"]:
    rho, p = stats.spearmanr(df.chng, df[c], nan_policy="omit")
    print(f"  chng vs {c:5s}: rho={rho:+.3f} p={p:.1e}")

print("\n== Базовая линия (все сигналы) ==")
for h in HORIZ:
    x = df[h]
    print(f"  {h:5s}: mean={x.mean():+.3f}% median={x.median():+.3f}% win(>0)={(x>0).mean()*100:.1f}% n={len(x)}")
print(f"  mfe24 mean={df.mfe24.mean():.2f}%  mae24 mean={df.mae24.mean():.2f}%")

FEATS = ["lbor", "lrep", "br", "chng", "lnet", "rank", "n24h", "n4h", "dbr", "b1h", "b4h", "vol_ratio"]
print("\n== Spearman-корреляция признаков с будущей доходностью ==")
hdr = f"{'feat':10s}" + "".join(f"{h:>16s}" for h in HORIZ)
print(hdr)
for f in FEATS:
    line = f"{f:10s}"
    for h in HORIZ:
        m = df[[f, h]].dropna()
        rho, p = stats.spearmanr(m[f], m[h])
        star = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
        line += f"{rho:+.3f}{star:3s}({p:.0e}) "
    print(line)

def buckets(f, q=5, label=None):
    m = df.dropna(subset=[f]).copy()
    try:
        m["q"] = pd.qcut(m[f], q, duplicates="drop")
    except Exception:
        return
    g = m.groupby("q", observed=True)
    out = g.agg(n=("r1h", "size"), r1h=("r1h", "mean"), w1h=("r1h", lambda x: (x > 0).mean() * 100),
                r4h=("r4h", "mean"), w4h=("r4h", lambda x: (x > 0).mean() * 100),
                r24h=("r24h", "mean"), w24h=("r24h", lambda x: (x > 0).mean() * 100),
                med24=("r24h", "median"))
    print(f"\n-- {label or f} по квантилям --")
    print(out.round(2).to_string())

for f in ["br", "chng", "lbor", "lnet", "dbr", "b1h", "n24h"]:
    buckets(f)

print("\n== Знак CHNG ==")
g = df.groupby("chng_sign")
print(g.agg(n=("r1h", "size"), r1h=("r1h", "mean"), r4h=("r4h", "mean"), r24h=("r24h", "mean"),
            w1h=("r1h", lambda x: (x > 0).mean() * 100), w24h=("r24h", lambda x: (x > 0).mean() * 100)).round(2))

print("\n== Комбинации (правила) ==")
def rule(name, mask):
    m = df[mask]
    if len(m) < 15:
        print(f"  {name:45s} n={len(m):4d}  (мало данных)"); return
    out = f"  {name:45s} n={len(m):4d} "
    for h in ["r1h", "r4h", "r24h"]:
        x = m[h]
        tt = stats.ttest_1samp(x, 0)
        out += f"| {h} {x.mean():+.2f}% win {(x>0).mean()*100:.0f}% p={tt.pvalue:.2f} "
    print(out)
q = df.br.quantile; qc = df.chng.quantile; ql = df.lbor.quantile
rule("br высокий (>q80)", df.br > q(.8))
rule("br низкий (<q20)", df.br < q(.2))
rule("chng>0", df.chng > 0)
rule("chng<0", df.chng < 0)
rule("chng сильно + (>q90)", df.chng > qc(.9))
rule("chng сильно - (<q10)", df.chng < qc(.1))
rule("br высокий & chng>0", (df.br > q(.8)) & (df.chng > 0))
rule("br высокий & chng<0", (df.br > q(.8)) & (df.chng < 0))
rule("br низкий & chng>0", (df.br < q(.2)) & (df.chng > 0))
rule("br низкий & chng<0", (df.br < q(.2)) & (df.chng < 0))
rule("первое появление за 24ч", df.first24 == 1)
rule("первое появление & chng>0", (df.first24 == 1) & (df.chng > 0))
rule("первое появление & chng<0", (df.first24 == 1) & (df.chng < 0))
rule("повтор >=6 раз за 24ч", df.n24h >= 6)
rule("bor большой (>q80)", df.lbor > ql(.8))
rule("bor большой & chng>0", (df.lbor > ql(.8)) & (df.chng > 0))
rule("bor большой & chng<0", (df.lbor > ql(.8)) & (df.chng < 0))
rule("dbr растёт (>0)", df.dbr > 0)
rule("dbr падает (<0)", df.dbr < 0)
rule("уже выросла 1ч (b1h>2%)", df.b1h > 2)
rule("уже упала 1ч (b1h<-2%)", df.b1h < -2)
rule("уже выросла 1ч & chng>0", (df.b1h > 2) & (df.chng > 0))
rule("rank 1 (первая строка)", df["rank"] == 1)

print("\n== По монетам: сколько сигналов и средний r24h ==")
g = df.groupby("sym").agg(n=("r1h", "size"), r1h=("r1h", "mean"), r24h=("r24h", "mean"), br=("br", "median"), chng=("chng", "mean")).sort_values("n", ascending=False)
print(g.head(25).round(2).to_string())
