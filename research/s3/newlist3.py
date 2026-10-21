"""«Слабый старт листинга»: через H часов после первой свечи нового фьючерса цена ≥ X% ниже максимума этих часов → шорт.
Сетка порогов/входа/выхода с итогом по 1-му и 2-му году и кварталам."""
import pickle, datetime, re, itertools
import numpy as np, pandas as pd
exec(open("s3/newlist2.py").read().split("rows = []")[0])
new = [(s, a) for s, a in K.items() if A <= a["t"][0] <= Bd and len(a["t"]) > 96 * 16]
res = []
for H, X, (tp, sl, hold) in itertools.product((12, 24, 48), (0.15, 0.25, 0.35), ((0.3, 0.3, 14), (0.2, 0.25, 7), (0.5, 0.5, 30), (0.3, 0.4, 21))):
    rows = []
    for s, a in new:
        j = H * 4; h = a["h"][:j + 1].astype(np.float64); c = float(a["c"][j])
        if c <= h.max() * (1 - X): rows.append((a["t"][0], short(s, j, tp, sl, hold * 96)))
    if len(rows) < 30: continue
    d = pd.DataFrame(rows, columns=["t", "p"]); d["y"] = np.where(d.t < CUT, 1, 2); d["q"] = pd.to_datetime(d.t, unit="s").dt.to_period("Q").astype(str)
    qm = d.groupby("q").p.mean()
    res.append((H, f"≥ {X:.0%}", f"{tp:.0%}/{sl:.0%}/{hold} дн.", len(d), round(d.p.mean() * 100, 2), round(d[d.y == 1].p.mean() * 100, 2), round(d[d.y == 2].p.mean() * 100, 2),
                round((d.p > 0).mean() * 100), f"{(qm > 0).sum()}/{len(qm)}"))
pd.set_option("display.width", 250)
print(pd.DataFrame(res, columns=["вход через, ч", "ниже максимума", "выход", "сделок", "итог %", "1-й год", "2-й год", "в плюсе %", "кв.+"]).to_string(index=False))
