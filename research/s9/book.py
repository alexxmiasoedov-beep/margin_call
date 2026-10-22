"""Логика лимитов автора на стакане фьючерса Binance (bookDepth, 15-мин средние): имбаланс (B−A)/(B+A) на глубинах 1…5%,
зоны ±0,5 (у автора — 3%), z-score бидов/асков за 14 суток («> 5 — сильный перевес»), градиент «1% против 5%», динамика
«цена падает, а имбаланс растёт». Исходы: доход за 4 / 24 ч, сделка тейк/стоп 2/2 и 3/3% (BTC), 3/3 и 5/5% (ETH)."""
import pickle, sys, datetime
import numpy as np, pandas as pd
SYM = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"; kname = SYM.replace("USDT", "")
Z = np.load(f"s9/bd/{SYM}.npz"); K = pickle.load(open("s2/k2y.pkl", "rb"))[kname]
bt = Z["t"]; Bd = Z["mean"][:, :5]; Ad = Z["mean"][:, 5:]
t = K["t"]; c = K["c"].astype(np.float64); h = K["h"].astype(np.float64); l = K["l"].astype(np.float64)
ix = np.searchsorted(t, bt); ok = (ix < len(t)) & (t[np.minimum(ix, len(t) - 1)] == bt); bt, Bd, Ad, ix = bt[ok], Bd[ok], Ad[ok], ix[ok]
imb = (Bd - Ad) / (Bd + Ad)
df = pd.DataFrame({"t": bt + 900, "j": ix})
for d in range(5): df[f"imb{d+1}"] = imb[:, d]
W = 14 * 96
for d in (1, 3, 5):
    for side, X in (("b", Bd[:, d - 1]), ("a", Ad[:, d - 1])):
        s = pd.Series(X); df[f"z{side}{d}"] = (s - s.rolling(W, min_periods=W // 2).mean().shift(1)) / s.rolling(W, min_periods=W // 2).std().shift(1)
df["grad"] = df.imb1 - df.imb5
df["d_imb3"] = df.imb3 - df.imb3.shift(16); df["r4p"] = c[df.j] / c[np.maximum(df.j - 16, 0)] - 1
f = lambda n: c[np.minimum(df.j + n, len(c) - 1)] / c[df.j] - 1
df["f4"], df["f24"] = f(16), f(96)
def trade(j, tp, sl, side, hold=96):
    e = c[j]; hi = h[j + 1:j + 1 + hold] / e - 1; lo = l[j + 1:j + 1 + hold] / e - 1
    if side > 0: g = np.flatnonzero(hi >= tp); b = np.flatnonzero(lo <= -sl)
    else: g = np.flatnonzero(lo <= -tp); b = np.flatnonzero(hi >= sl)
    gq = g[0] if len(g) else 10**9; bq = b[0] if len(b) else 10**9
    if bq <= gq and bq < 10**9: return -sl - 0.001
    if gq < 10**9: return tp - 0.001
    x = c[min(j + hold, len(c) - 1)] / e - 1; return side * x - 0.001
TPS = (0.02, 0.03) if kname == "BTC" else (0.03, 0.05)
CUT = datetime.datetime(2025, 10, 15, tzinfo=datetime.timezone.utc).timestamp(); df["half"] = np.where(df.t < CUT, 1, 2)
df = df.dropna(subset=["imb3"]).reset_index(drop=True)
print(f"===== {SYM}: {len(df)} свечей; имбаланс 3%: перцентили 1/5/50/95/99 =", np.percentile(df.imb3, [1, 5, 50, 95, 99]).round(3))
def show(nm, m, side):
    g = df[m]
    if len(g) < 30: return
    # не чаще раза в 4 ч
    keep, last = [], -10**9
    for i, j in zip(g.index, g.j):
        if j - last >= 16: keep.append(i); last = j
    g = g.loc[keep]; h1, h2 = g[g.half == 1], g[g.half == 2]
    tr = {tp: np.array([trade(j, tp, tp, side) for j in g.j]) for tp in TPS}
    print(f"  {nm:52s} n={len(g):5d} за 4 ч {side*g.f4.mean()*100:+.3f}% ({side*h1.f4.mean()*100:+.3f}/{side*h2.f4.mean()*100:+.3f}) за 24 ч {side*g.f24.mean()*100:+.3f}% | "
          + " ".join(f"{int(tp*100)}/{int(tp*100)}: {v.mean()*100:+.2f}% WR {(v > 0).mean():.0%}" for tp, v in tr.items()))
q = {d: np.percentile(df[f"imb{d}"], [5, 95]) for d in (1, 3, 5)}
show("ВСЕ свечи — лонг", df.imb3 > -9, 1); show("ВСЕ свечи — шорт", df.imb3 > -9, -1)
for d in (1, 3, 5):
    show(f"имбаланс {d}% ≥ +0,5 → лонг", df[f"imb{d}"] >= 0.5, 1); show(f"имбаланс {d}% ≤ −0,5 → шорт", df[f"imb{d}"] <= -0.5, -1)
    show(f"имбаланс {d}% ≥ 95-й перц. ({q[d][1]:.2f}) → лонг", df[f"imb{d}"] >= q[d][1], 1)
    show(f"имбаланс {d}% ≤ 5-й перц. ({q[d][0]:.2f}) → шорт", df[f"imb{d}"] <= q[d][0], -1)
for d in (1, 3):
    show(f"z бидов {d}% ≥ 3 → лонг", df[f"zb{d}"] >= 3, 1); show(f"z асков {d}% ≥ 3 → шорт", df[f"za{d}"] >= 3, -1)
    show(f"z бидов {d}% ≥ 5 → лонг", df[f"zb{d}"] >= 5, 1); show(f"z асков {d}% ≥ 5 → шорт", df[f"za{d}"] >= 5, -1)
show("градиент (1% − 5%) ≥ 95-й перц. → лонг", df.grad >= df.grad.quantile(0.95), 1); show("градиент ≤ 5-й перц. → шорт", df.grad <= df.grad.quantile(0.05), -1)
show("цена за 4 ч ≤ −2%, имбаланс 3% вырос ≥ +0,2 → лонг", (df.r4p <= -0.02) & (df.d_imb3 >= 0.2), 1)
show("цена за 4 ч ≥ +2%, имбаланс 3% упал ≤ −0,2 → шорт", (df.r4p >= 0.02) & (df.d_imb3 <= -0.2), -1)
show("цена за 4 ч ≤ −2%, имбаланс 3% упал ≤ −0,2 → шорт (по тренду)", (df.r4p <= -0.02) & (df.d_imb3 <= -0.2), -1)
