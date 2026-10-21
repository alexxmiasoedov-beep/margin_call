"""Лонг «памп без розницы»: сетка (доля спота × порог Кореи × порог лиры × выход), выбор по 1-му году → проверка на 2-м."""
import pickle, itertools
import numpy as np, pandas as pd
src = open("s5/venue_share.py").read()
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
exec("def fund(" + src.split("def fund(")[1].split("rows = []")[0])
H = pd.read_pickle("s5/lowspot_var.pkl")
H = H[H.share < 0.2].copy()
EX = [(0.3, 0.15, 192), (0.2, 0.1, 192), (0.5, 0.2, 288), (0.3, 0.2, 288), (0.15, 0.1, 96)]
for e in EX: H[str(e)] = [trade(s, j, 1, e[0], e[1], e[2]) for s, j in zip(H.s, H.j)]
ks = H.kshare.fillna(0).where(H.korea, 0); fs = H.fshare.fillna(0).where(H.fhas, 0)
res = []
for X, KR, TR, e in itertools.product((0.06, 0.08, 0.1, 0.12, 0.15), (0.05, 0.1, 0.2), (0.03, 0.05, 0.1), EX):
    g = H[(H.share < X) & (ks < KR) & (fs < TR)]
    if len(g) < 40: continue
    e = str(e) if isinstance(e, tuple) else e; ee = eval(e); qm = g.groupby("q")[e].mean()
    res.append((X, KR, TR, f"{ee[0]:g}/{ee[1]:g}/{ee[2] // 4}ч", len(g), g[g.y == 1][e].mean() * 100, g[g.y == 2][e].mean() * 100, (g.y == 2).sum(), (qm > 0).sum(), len(qm)))
R = pd.DataFrame(res, columns=["спот<", "Корея<", "лира<", "выход", "n", "1-й", "2-й", "n2", "кв+", "кв"])
print(f"вариантов {len(R)}; 2-й год в плюсе у {(R['2-й'] > 0).sum()} ({(R['2-й'] > 0).mean():.0%}); средний 2-й год {R['2-й'].mean():+.2f}%; корреляция рангов {R['1-й'].rank().corr(R['2-й'].rank()):.2f}")
top = R.sort_values("1-й", ascending=False)
print("10 лучших по 1-му году:"); print(top.head(10).round(2).to_string(index=False))
print("среднее 2-го года у 10 лучших по 1-му:", round(top.head(10)["2-й"].mean(), 2), "| у 10 худших:", round(top.tail(10)["2-й"].mean(), 2))
print()
for X, KR, TR in ((0.1, 0.1, 0.05), (0.12, 0.2, 0.1), (0.1, 0.2, 0.1), (0.12, 0.1, 0.05)):
    print(R[(R["спот<"] == X) & (R["Корея<"] == KR) & (R["лира<"] == TR)].round(2).to_string(index=False, header=(X == 0.1 and KR == 0.1)))
H.to_pickle("s5/lowspot_tt.pkl")
