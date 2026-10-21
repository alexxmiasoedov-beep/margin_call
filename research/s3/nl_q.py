import pickle, datetime
import numpy as np, pandas as pd
exec(open("s3/newlist_final.py").read().split("T = []")[0])
rows = []
for s, a in K.items():
    if not (A <= a["t"][0] <= Bd) or len(a["t"]) < 96 * 3: continue
    j = 96; hmax = float(a["h"][:j + 1].max()); c = float(a["c"][j]); weak = c <= hmax * 0.75
    p, fd, how, tout = short2(s, j, 0.3, 0.4, 21 * 96)
    rows.append(dict(s=s, t=a["t"][j] + 900, out=tout, p=p, weak=weak, how=how))
D = pd.DataFrame(rows); D["q"] = pd.to_datetime(D.t, unit="s").dt.to_period("Q").astype(str)
g = D.groupby("q").agg(listings=("s", "size"), weak=("weak", "sum"))
g["weak_pnl"] = D[D.weak].groupby("q").p.mean() * 100; g["other_pnl"] = D[~D.weak].groupby("q").p.mean() * 100
print(g.round(1).to_string())
W = D[D.weak].sort_values("t"); u = W.p.values * 10; eq = np.cumsum(u); dd = (eq - np.maximum.accumulate(eq)).min()
print(f"30/40/21: {len(W)} сделок, {W.p.mean()*100:+.2f}%, в плюсе {(W.p>0).mean():.0%}, итог {u.sum():+.1f} USDT, просадка {dd:+.1f}; исходы", W.how.value_counts().to_dict())
m = W.groupby(pd.to_datetime(W.t, unit="s").dt.to_period("M")).p.sum() * 10
print("месяцев в плюсе", (m > 0).sum(), "из", len(m)); print(m.round(1).to_string())
