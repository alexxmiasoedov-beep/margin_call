"""Варианты лонга «памп без спотовой розницы»: спот у монеты обычно есть (обычная доля ≥ 3%), разные пороги «нет корейцев / турок»."""
import pickle
import numpy as np, pandas as pd
src = open("s5/venue_share.py").read()
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
exec("def fund(" + src.split("def fund(")[1].split("rows = []")[0])
D = pd.read_pickle("s5/pump_spot.pkl"); H = D[D.has & (D.norm >= 0.03)].copy()
H["q"] = pd.to_datetime(H.t, unit="s").dt.to_period("Q").astype(str); H["j"] = [int(np.searchsorted(K[s]["t"], t - 900)) for s, t in zip(H.s, H.t)]
H["p"] = [trade(s, j, 1, 0.3, 0.15, 192) for s, j in zip(H.s, H.j)]
ks = H.kshare.fillna(0).where(H.korea, 0); fs = H.fshare.fillna(0).where(H.fhas, 0)
def show(nm, g):
    qm = g.groupby("q").p.mean()
    print(f"{nm:52s} {len(g):4d} | {g.p.mean()*100:+.2f}% ({g[g.y==1].p.mean()*100:+.2f}/{g[g.y==2].p.mean()*100:+.2f}) | в плюсе {(g.p>0).mean():.0%} | кв.+ {(qm>0).sum()}/{len(qm)}")
for X in (0.10, 0.12, 0.15):
    low = H.share < X
    show(f"доля спота < {X:.0%}, Корея < 20%, лира < 10%", H[low & (ks < 0.2) & (fs < 0.1)])
    show(f"доля спота < {X:.0%}, Корея < 10%, лира < 5%", H[low & (ks < 0.1) & (fs < 0.05)])
    show(f"доля спота < {X:.0%}, Корея < 5%, лира < 3%", H[low & (ks < 0.05) & (fs < 0.03)])
    show(f"доля спота < {X:.0%}, без фильтра Кореи/Турции", H[low])
    show(f"доля спота < {X:.0%}, но Корея ≥ 20% или лира ≥ 10%", H[low & ((ks >= 0.2) | (fs >= 0.1))])
H.to_pickle("s5/lowspot_var.pkl")
