"""Рыночный фон займов (z суммарного BOR альтов за 30 дней): сколько дней даёт эффект, не обвалы ли это, контроль по BTC."""
import numpy as np, pandas as pd
E = pd.read_pickle("s9/md_events.pkl"); M = pd.read_pickle("s10/ev_margin.pkl")
D = E.merge(M, on=["s", "t"], how="left")
D["day"] = pd.to_datetime(D.t, unit="s").dt.strftime("%Y-%m-%d")
def dedup(g, h=24):
    g = g.sort_values("t"); keep = []; last = {}
    for i, s, t in zip(g.index, g.s, g.t):
        if t - last.get(s, -1e18) >= h * 3600: keep.append(i); last[s] = t
    return g.loc[keep]
g = dedup(D[D.ev == "ENTER"])
hi = g[g.mkt_bz >= 1.5]
dd = hi.groupby("day").agg(n=("s", "size"), L=("L_20_10", "mean"), S=("S_10_25", "mean"), btc=("btc24", "mean"), r24=("c_r24", "mean"))
print("ENTER при фоне z ≥ 1,5:", len(hi), "событий в", len(dd), "днях")
print(dd.sort_values("n", ascending=False).head(15).round(3).to_string())
top = dd.sort_values("n", ascending=False).index[:5]
rest = hi[~hi.day.isin(top)]
print(f"без 5 самых насыщенных дней: n={len(rest)} L_20_10 {rest.L_20_10.mean()*100:+.2f}% S_10_25 {rest.S_10_25.mean()*100:+.2f}%")
print("по месяцам (L_20_10, n):"); print(hi.groupby(pd.to_datetime(hi.t, unit="s").dt.strftime("%y%m")).L_20_10.agg(["mean", "size"]).round(3).T.to_string())
for nm, m in (("BTC за сутки < −2%", hi.btc24 < -0.02), ("BTC за сутки −2…+2%", hi.btc24.abs() <= 0.02), ("BTC за сутки > +2%", hi.btc24 > 0.02)):
    x = hi[m]; print(f"{nm:22s} n={len(x):4d} L_20_10 {x.L_20_10.mean()*100:+.2f}% S_10_25 {x.S_10_25.mean()*100:+.2f}%")
# сам фон: сколько времени он ≥ 1,5 и что делает рынок альтов после
