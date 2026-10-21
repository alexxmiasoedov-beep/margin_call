"""Лонг пампа, который делает фьючерс, а не спот: доля спота Binance за час < X, без корейской/турецкой розницы.
Сетка порога и выхода: итог по 1-му и 2-му году, кварталы; выбор на 1-м году → проверка на 2-м."""
import pickle, re, datetime
import numpy as np, pandas as pd
src = open("s5/venue_share.py").read()
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
exec("def fund(" + src.split("def fund(")[1].split("rows = []")[0])
D = pd.read_pickle("s5/pump_spot.pkl"); H = D[D.has].copy()
H["kt"] = (H.korea & (H.kshare >= 0.2)) | (H.fhas & (H.fshare >= 0.1)); H = H[~H.kt]
H["q"] = pd.to_datetime(H.t, unit="s").dt.to_period("Q").astype(str)
H["j"] = [int(np.searchsorted(K[s]["t"], t - 900)) for s, t in zip(H.s, H.t)]
EX = [(0.1, 0.1, 96), (0.2, 0.1, 192), (0.3, 0.15, 192), (0.5, 0.2, 288), (0.3, 0.2, 288), (9, 0.15, 192), (9, 9, 96), (9, 9, 192)]
for tp, sl, hold in EX:
    H[f"p{tp}_{sl}_{hold}"] = [trade(s, j, 1, tp, sl, hold) for s, j in zip(H.s, H.j)]
H.to_pickle("s5/lowspot_trades.pkl")
res = []
for X in (0.05, 0.08, 0.1, 0.12, 0.15, 0.2, 0.25):
    g = H[H.share < X]
    for tp, sl, hold in EX:
        c = f"p{tp}_{sl}_{hold}"; qm = g.groupby("q")[c].mean()
        res.append((X, f"{tp:g}/{sl:g}/{hold // 4}ч", len(g), g[c].mean() * 100, g[g.y == 1][c].mean() * 100, g[g.y == 2][c].mean() * 100,
                    (g[c] > 0).mean() * 100, f"{(qm > 0).sum()}/{len(qm)}"))
R = pd.DataFrame(res, columns=["доля <", "выход", "n", "итог", "1-й", "2-й", "плюс%", "кв+"])
pd.set_option("display.width", 200); print(R.round(2).to_string(index=False))
print("\nкорреляция рангов вариантов 1-й/2-й год:", round(R["1-й"].rank().corr(R["2-й"].rank()), 2), "| 2-й год в плюсе:", (R["2-й"] > 0).sum(), "из", len(R))
best = R.sort_values("1-й", ascending=False).head(5); print("лучшие по 1-му году:\n", best.round(2).to_string(index=False))
