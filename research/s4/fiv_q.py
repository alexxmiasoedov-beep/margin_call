import pickle, datetime
import numpy as np, pandas as pd
exec(open("s4/fiv_trade.py").read().split("E = D[")[0])
E = D[(D.kind == "короче") & (D.rate < 0)].copy()
for tp, sl, hold in ((9, 0.3, 288), (9, 9, 288), (9, 0.2, 288), (9, 0.15, 96)):
    r = [trade(x.s, x.t, 1, tp, sl, hold) for x in E.itertuples()]; E["p"] = [a for a, b in r]; E["fd"] = [b for a, b in r]
    E["q"] = pd.to_datetime(E.t, unit="s").dt.to_period("Q").astype(str)
    srt = E.p.sort_values(ascending=False)
    bys = E.groupby("s").p.sum().sort_values(ascending=False)
    print(f"\nЛОНГ стоп {sl:.0%} {hold/96:.0f} дн: {E.p.mean()*100:+.2f}%, без 10 лучших сделок {srt.iloc[10:].mean()*100:+.2f}%, без 20 {srt.iloc[20:].mean()*100:+.2f}%, "
          f"монет в плюсе {(bys>0).sum()}/{len(bys)}; лучшие: " + ", ".join(f"{k} {v*100:+.0f}%" for k, v in bys.head(6).items()))
    print("  кварталы:", " | ".join(f"{q} {g.p.mean()*100:+.1f}% ({len(g)})" for q, g in E.groupby("q")))
    print("  цена без фандинга:", f"{(E.p - E.fd).mean()*100:+.2f}%, фандинг {E.fd.mean()*100:+.2f}%")
