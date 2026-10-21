"""Лонг «памп без спотовой розницы»: доля спота Binance за час < 12%, корейцев < 20%, лиры < 10%; тейк 30 / стоп 15 / 48 ч.
Месяцы, просадка, одновременные позиции, концентрация по монетам и сделкам, сравнение с остальными пампами."""
import pickle, datetime
import numpy as np, pandas as pd
H = pd.read_pickle("s5/lowspot_trades.pkl"); c = "p0.3_0.15_192"
K = pickle.load(open("s2/k2y.pkl", "rb"))
for X in (0.10, 0.12):
    g = H[H.share < X].sort_values("t").copy(); o = H[H.share >= X]
    u = g[c].values * 10; eq = np.cumsum(u); dd = (eq - np.maximum.accumulate(eq)).min()
    mo = g.groupby(pd.to_datetime(g.t, unit="s").dt.to_period("M"))[c].sum() * 10
    bys = g.groupby("s")[c].sum().sort_values(ascending=False); srt = g[c].sort_values(ascending=False)
    top = set(bys.index[:max(1, len(bys) // 20)])
    print(f"\n=== доля спота < {X:.0%}: {len(g)} сделок, {g.s.nunique()} монет, {g[c].mean()*100:+.2f}% на сделку, в плюсе {(g[c]>0).mean():.0%}, итог {u.sum():+.1f} USDT (1 × 10), "
          f"просадка {dd:+.1f}, месяцев в плюсе {(mo>0).sum()}/{len(mo)}")
    print(f"   без 1% лучших сделок {srt.iloc[len(g)//100:].mean()*100:+.2f}%, без 5% {srt.iloc[len(g)//20:].mean()*100:+.2f}% | без 5% лучших монет {g[~g.s.isin(top)][c].mean()*100:+.2f}% | монет в плюсе {(bys>0).sum()}/{len(bys)}")
    print(f"   остальные пампы (доля ≥ {X:.0%}, без KR/TR): {len(o)} сделок, {o[c].mean()*100:+.2f}% ({o[o.y==1][c].mean()*100:+.2f}/{o[o.y==2][c].mean()*100:+.2f})")
    print("   лучшие монеты:", ", ".join(f"{k} {v*100:+.0f}%" for k, v in bys.head(8).items()))
    print("   месяцы:", " ".join(f"{str(k)[2:]}:{v:+.1f}" for k, v in mo.items()))
    # исходы
    hit_tp = (g[c] > 0.29).mean(); hit_sl = (g[c] < -0.14).mean(); print(f"   тейк {hit_tp:.0%}, стоп {hit_sl:.0%}, по времени {1 - hit_tp - hit_sl:.0%}")
