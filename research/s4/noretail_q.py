import numpy as np, pandas as pd
exec(open("s4/kr_absent_long.py").read().split("G = {")[0])
g = P[~P.korea & ~(P.has & (P.fshare >= 0.03))].copy()
for tp, sl, hold in ((0.3, 0.2, 288), (9, 9, 192), (0.3, 0.15, 192)):
    g["p"] = [trade(x.s, x.t, 1, tp, sl, hold) for x in g.itertuples()]; h = g.dropna(subset=["p"]).sort_values("t")
    h["q"] = pd.to_datetime(h.t, unit="s").dt.to_period("Q").astype(str); h["mo"] = pd.to_datetime(h.t, unit="s").dt.to_period("M")
    srt = h.p.sort_values(ascending=False); n1 = len(h) // 100
    mo = h.groupby("mo").p.sum()
    u = h.p.values * 10; eq = np.cumsum(u); dd = (eq - np.maximum.accumulate(eq)).min()
    print(f"\nЛОНГ {tp:.0%}/{sl:.0%}/{hold/4:.0f} ч: {len(h)} сделок, {h.p.mean()*100:+.2f}%, без 1% лучших ({n1}) {srt.iloc[n1:].mean()*100:+.2f}%, без 5% {srt.iloc[5*n1:].mean()*100:+.2f}%, "
          f"месяцев в плюсе {(mo>0).sum()}/{len(mo)}, просадка {dd:+.0f} USDT при итоге {u.sum():+.0f}")
    print("  кварталы:", " | ".join(f"{q} {x.p.mean()*100:+.1f}% ({len(x)})" for q, x in h.groupby("q")))
