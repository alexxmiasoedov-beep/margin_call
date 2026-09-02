import json, os, bisect, subprocess
import numpy as np, pandas as pd
from scipy import stats
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)

df = pd.read_csv("dataset.csv").sort_values("epoch").reset_index(drop=True)
sig = pd.read_csv("signals.csv")

# --- BTC as market reference ---
if not os.path.exists("klines/_BTC.json"):
    t0 = int(df.epoch.min()) - 6 * 3600; out = []; start = t0 * 1000
    import time
    while True:
        j = json.loads(subprocess.run(["curl", "-sS", f"https://api.mexc.com/api/v3/klines?symbol=BTCUSDT&interval=15m&startTime={start}&limit=1000"], capture_output=True, text=True).stdout)
        if not j: break
        out += [(int(k[0]) // 1000, float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])) for k in j]
        if len(j) < 1000: break
        start = int(j[-1][0]) + 900000
    json.dump({"src": "mexc", "k": out}, open("klines/_BTC.json", "w"))
kb = np.array(json.load(open("klines/_BTC.json"))["k"]); tb = kb[:, 0].astype(int)
HORIZ = {"r1h": 4, "r4h": 16, "r12h": 48, "r24h": 96}
for name, n in HORIZ.items():
    vals = []
    for e in df.epoch:
        i = bisect.bisect_right(tb, e) - 1
        vals.append((kb[i + n, 4] / kb[i + 1, 1] - 1) * 100 if i + n < len(kb) else np.nan)
    df["btc_" + name] = vals
print("BTC за период:", f"{(kb[-1,4]/kb[0,1]-1)*100:+.1f}%", pd.to_datetime(kb[0,0], unit='s'), "→", pd.to_datetime(kb[-1,0], unit='s'))
print("BTC суточные:");
daily = pd.Series(kb[:, 4], index=pd.to_datetime(kb[:, 0], unit="s")).resample("1D").last().pct_change() * 100
print(daily.round(2).to_string())

# exclude stable-like symbols (no price movement)
vol = df.groupby("sym").r24h.std()
stable = vol[vol < 0.15].index.tolist()
print("\nисключаю как стейблы/без движения:", stable)
df = df[~df.sym.isin(stable)].copy()

# cross-sectional neutralization: subtract the median return of all coins posted in the same hour
df["hour"] = df.epoch // 3600
for h in HORIZ:
    df["x" + h] = df[h] - df["btc_" + h]           # excess over BTC
    df["c" + h] = df[h] - df.groupby("hour")[h].transform("median")  # vs peers in the same hour

# --- what is CHNG? compare with changes of bor/rep/br vs previous appearance ---
sig = sig.sort_values(["sym", "epoch"])
sig["dbor"] = sig.groupby("sym").bor.pct_change() * 100
sig["drep"] = sig.groupby("sym").rep.pct_change() * 100
sig["dbr"] = sig.groupby("sym").br.diff()
sig["dbr_pct"] = sig.groupby("sym").br.pct_change() * 100
sig["gap_min"] = sig.groupby("sym").epoch.diff() / 60
print("\n== CHNG vs изменения своих же колонок (Spearman) ==")
for c in ["dbor", "drep", "dbr", "dbr_pct"]:
    m = sig[[c, "chng"]].replace([np.inf, -np.inf], np.nan).dropna()
    print(f"  chng vs {c:8s}: rho={stats.spearmanr(m[c], m.chng)[0]:+.3f}  n={len(m)}")
print("  распределение chng:", sig.chng.describe().round(3).to_dict())
print("  примеры строк с большим |chng|:")
print(sig[sig.chng.abs() > 3][["ts", "sym", "bor", "rep", "br", "chng", "dbor", "dbr"]].head(12).to_string())

def report(d, label, cols=("r1h", "r4h", "r24h", "xr4h", "xr24h", "cr4h", "cr24h")):
    out = f"  {label:42s} n={len(d):5d} "
    for c in cols:
        x = d[c].dropna()
        if len(x) < 10:
            out += f"| {c} n/a "; continue
        p = stats.ttest_1samp(x, 0).pvalue
        out += f"| {c} {x.mean():+.2f}%/{(x>0).mean()*100:.0f}%{'*' if p<0.05 else ' '}"
    print(out)

print("\n== Все строки (без стейблов), сырые / сверх BTC (x) / относительно соседей по часу (c) ==")
report(df, "baseline")

# --- independent episodes: first appearance of a symbol after >= GAP hours of silence ---
GAP = 4 * 3600
df["prev_epoch"] = df.groupby("sym").epoch.shift()
df["gap"] = df.epoch - df.prev_epoch
ep = df[(df.gap.isna()) | (df.gap >= GAP)].copy()
print(f"\n== Эпизоды: первое появление монеты после >= {GAP//3600}ч тишины: n={len(ep)} ==")
report(ep, "все эпизоды")
q = ep.br.quantile
report(ep[ep.br > q(.75)], "br верхняя четверть (>%.1f)" % q(.75))
report(ep[ep.br < q(.25)], "br нижняя четверть (<%.1f)" % q(.25))
report(ep[ep.chng > 0], "chng>0")
report(ep[ep.chng < 0], "chng<0")
report(ep[ep.chng == 0], "chng=0")
report(ep[ep.b4h > 3], "уже +3% за 4ч до поста")
report(ep[ep.b4h < -3], "уже -3% за 4ч до поста")
report(ep[(ep.b4h > 3) & (ep.br > q(.5))], "уже +3% за 4ч & br выше медианы")
report(ep[(ep.b4h < -3) & (ep.br > q(.5))], "уже -3% за 4ч & br выше медианы")
report(ep[ep.lbor > ep.lbor.quantile(.75)], "bor верхняя четверть")
report(ep[ep.lbor < ep.lbor.quantile(.25)], "bor нижняя четверть")
report(ep[ep["rank"] == 1], "rank 1")
report(ep[ep.vol_ratio > 2], "объём свечи >2x среднего 4ч")

print("\n== Эпизоды: Spearman признаков с доходностью сверх BTC ==")
FE = ["lbor", "lrep", "br", "chng", "lnet", "rank", "b1h", "b4h", "vol_ratio"]
print(f"{'feat':10s}" + "".join(f"{h:>14s}" for h in ["xr1h", "xr4h", "xr12h", "xr24h", "cr4h", "cr24h"]))
for f in FE:
    line = f"{f:10s}"
    for h in ["xr1h", "xr4h", "xr12h", "xr24h", "cr4h", "cr24h"]:
        m = ep[[f, h]].dropna()
        rho, p = stats.spearmanr(m[f], m[h])
        line += f"{rho:+.3f}{'*' if p<0.05 else ' '}({p:.2f})  "
    print(line)

# --- streak dynamics: how does a symbol behave over the course of a run of appearances ---
df["run_id"] = ((df.gap.isna()) | (df.gap >= GAP)).cumsum()
df["run_pos"] = df.groupby("run_id").cumcount()
df["run_len"] = df.groupby("run_id").run_pos.transform("max") + 1
df["run_hours"] = (df.epoch - df.groupby("run_id").epoch.transform("min")) / 3600
print("\n== Динамика внутри серии появлений (сколько часов монета уже висит в канале) ==")
bins = [-0.01, 0.5, 2, 6, 12, 24, 1000]
g = df.groupby(pd.cut(df.run_hours, bins), observed=True)
print(g.agg(n=("r4h", "size"), r4h=("r4h", "mean"), xr4h=("xr4h", "mean"), r24h=("r24h", "mean"), xr24h=("xr24h", "mean"),
            w24=("xr24h", lambda x: (x > 0).mean() * 100), b4h=("b4h", "mean")).round(2).to_string())

# --- exit of a symbol: last appearance before >= GAP silence ---
df["next_epoch"] = df.groupby("sym").epoch.shift(-1)
df["gap_next"] = df.next_epoch - df.epoch
last = df[(df.gap_next >= GAP)].copy()
print(f"\n== Последнее появление перед >= 4ч тишины (монета «уходит» из канала): n={len(last)} ==")
report(last, "все")
report(last[last.run_len >= 20], "после длинной серии (>=20 постов)")

# --- top coins per episode with details for eyeballing ---
print("\n== Топ эпизодов по |xr24h| ==")
cols = ["sym", "epoch", "bor", "rep", "br", "chng", "b4h", "r1h", "r4h", "r24h", "xr24h", "run_len"]
ep2 = df[(df.gap.isna()) | (df.gap >= GAP)]
show = ep2.assign(ts=pd.to_datetime(ep2.epoch, unit="s")).sort_values("xr24h")
print(show[["ts"] + cols[2:]].assign(sym=show.sym).set_index("sym").head(12).round(2).to_string())
print(show[["ts"] + cols[2:]].assign(sym=show.sym).set_index("sym").tail(12).round(2).to_string())
df.to_csv("dataset2.csv", index=False)
ep.to_csv("episodes.csv", index=False)
