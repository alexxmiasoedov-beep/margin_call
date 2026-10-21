"""Общая доля спота на момент пампа: спот Binance + OKX + KuCoin + Bitget + Coinbase (что есть у монеты) против фьючерса Binance.
Сравнение с одной долей спота Binance для лонга «памп без розницы» (Корея < 20%, лира < 10%), тейк 30 / стоп 15 / 48 ч."""
import json, os, re, pickle
import numpy as np, pandas as pd
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
K = pickle.load(open("s2/k2y.pkl", "rb"))
H = pd.read_pickle("s5/lowspot_tt.pkl")   # пампы со спотом Binance (обычная доля ≥ 3%), доля спота < 20%
fmt = {"cb": lambda x: (int(x[0]), float(x[5]) * float(x[4])), "ku": lambda x: (int(x[0]), float(x[6])),
       "bg": lambda x: (int(x[0]) // 1000, float(x[6])), "okx": lambda x: (int(x[0]) // 1000, float(x[7]))}
def other(s, t):
    c = strip(s); tot = 0.0; got = []
    for v, f in fmt.items():
        fn = f"s5/{v}/{c}_{int(t)}.json"
        if not os.path.exists(fn): continue
        j = json.load(open(fn))
        if not isinstance(j, list): continue
        vol = sum(q for tt, q in map(f, j) if t - 3600 <= tt < t); tot += vol
        if j: got.append(v)
    return tot, "+".join(got)
H["oth"], H["venues"] = zip(*[other(s, t) for s, t in zip(H.s, H.t)])
H["fut"] = [float(K[s]["qv"][j - 3:j + 1].astype(np.float64).sum()) for s, j in zip(H.s, H.j)]
H["bspot"] = H.share * H.fut / (1 - H.share).clip(lower=1e-9)
H["gshare"] = (H.bspot + H.oth) / (H.bspot + H.oth + H.fut)
ks = H.kshare.fillna(0).where(H.korea, 0); fs = H.fshare.fillna(0).where(H.fhas, 0); base = (ks < 0.2) & (fs < 0.1)
c = "(0.3, 0.15, 192)"
print(f"пампов {len(H)}; общая доля спота: медиана {H.gshare.median():.1%}; доп. площадки есть у {(H.venues != '').mean():.0%}")
for X in (0.12, 0.15, 0.2, 0.25):
    g = H[base & (H.gshare < X)]
    print(f"общая доля спота < {X:.0%}: {len(g)} сделок, лонг {g[c].mean()*100:+.2f}% ({g[g.y==1][c].mean()*100:+.2f}/{g[g.y==2][c].mean()*100:+.2f})")
g = H[base & (H.share < 0.12)]; print(f"для сравнения: только спот Binance < 12%: {len(g)} сделок, {g[c].mean()*100:+.2f}% ({g[g.y==1][c].mean()*100:+.2f}/{g[g.y==2][c].mean()*100:+.2f})")
for lo, hi in ((0, 0.12), (0.12, 0.2)):
    for glo, ghi in ((0, 0.15), (0.15, 1.01)):
        g = H[base & (H.share >= lo) & (H.share < hi) & (H.gshare >= glo) & (H.gshare < ghi)]
        if len(g): print(f"  спот Binance {lo:.0%}–{hi:.0%}, общая {glo:.0%}–{ghi:.0%}: {len(g)} сделок, {g[c].mean()*100:+.2f}% ({g[g.y==1][c].mean()*100:+.2f}/{g[g.y==2][c].mean()*100:+.2f})")
