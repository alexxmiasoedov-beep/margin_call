"""Фама–Макбет по рангам: доходность следующей недели (с фандингом, для лонга) на признаки, известные на входе.
Сравнение моделей без канала и с каналом; двойные сортировки; остаток фактора канала после ценовых признаков."""
import datetime
import numpy as np, pandas as pd
F = pd.read_pickle("s10/factor5.pkl")
UTC = datetime.timezone.utc; CUT = datetime.datetime(2025, 12, 1, tzinfo=UTC).timestamp()
F["y"] = F.ret - F.fr                      # доход лонга с фандингом; шорт = −y
F["inch"] = (F.sh > 0).astype(float)
F["lv"] = np.log(F.v)
PRICE = ["r1", "r7", "r30", "vol", "mx", "vchg", "f0", "fr7", "tbr", "lv"]
def zr(d, cols):
    out = d[cols].rank(pct=True) - 0.5
    return out.fillna(0.0)
def fm(cols, d=F, nm=""):
    B = []
    for W, g in d.groupby("W"):
        if len(g) < 30: continue
        X = zr(g, cols).values; X = np.column_stack([np.ones(len(g)), X]); y = g.y.values
        b = np.linalg.lstsq(X, y, rcond=None)[0]; B.append(np.r_[W, b[1:]])
    B = pd.DataFrame(B, columns=["W"] + cols).set_index("W")
    h = B.index < CUT
    print(f"\n{nm} (недель {len(B)}): коэффициент = разница доходности за неделю между верхом и низом ранга, %")
    for c in cols:
        x = B[c]; t = x.mean() / x.std() * np.sqrt(len(x))
        print(f"   {c:6s} {x.mean()*100:+6.2f}  t {t:+5.2f}   1-я/2-я {x[h].mean()*100:+6.2f}/{x[~h].mean()*100:+6.2f}")
    return B
fm(PRICE, nm="Только цена и фандинг")
fm(PRICE + ["sh"], nm="Цена + доля присутствия в канале")
fm(PRICE + ["inch", "sh"], nm="Цена + «в канале да/нет» + доля")
# Двойная сортировка: терцили по доходности за 7 дней × группы канала
print("\nДвойная сортировка: средняя доходность лонга за неделю с фандингом, % (в скобках — монет в среднем за неделю)")
F["r7t"] = F.groupby("W").r7.transform(lambda x: pd.qcut(x.rank(method="first"), 3, labels=["падали", "середина", "росли"]))
F["volt"] = F.groupby("W").vol.transform(lambda x: pd.qcut(x.rank(method="first"), 3, labels=["тихие", "средние", "буйные"]))
def grp(d):
    d = d.copy(); d["cg"] = "вне канала"
    inn = d.sh > 0
    d.loc[inn, "cg"] = d[inn].groupby("W").sh.transform(lambda x: pd.qcut(x.rank(method="first"), 2, labels=["в канале реже", "в канале чаще"]) if len(x) >= 4 else "в канале реже").astype(str)
    return d
F = grp(F)
for by in ("r7t", "volt"):
    T = F.groupby([by, "cg"], observed=True).agg(y=("y", "mean"), n=("y", "size"))
    T["n"] = T.n / F.W.nunique()
    piv = T.y.unstack() * 100; cnt = T.n.unstack()
    print(f"\nпо {'доходности за 7 дней' if by == 'r7t' else 'волатильности'}:")
    for i in piv.index:
        print(f"   {i:9s} " + "  ".join(f"{c}: {piv.loc[i, c]:+.2f} ({cnt.loc[i, c]:.0f})" for c in ["вне канала", "в канале реже", "в канале чаще"]))
# Остаток доли канала после ценовых признаков (по неделям), затем сортировка по остатку среди монет канала
res = []
for W, g in F[F.sh > 0].groupby("W"):
    if len(g) < 20: continue
    X = np.column_stack([np.ones(len(g)), zr(g, PRICE).values]); s = g.sh.rank(pct=True).values
    e = s - X @ np.linalg.lstsq(X, s, rcond=None)[0]
    res.append(pd.Series(e, index=g.index))
F["shres"] = pd.concat(res)
inn = F[F.shres.notna()].copy()
inn["q"] = inn.groupby("W").shres.transform(lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
q = inn.groupby(["W", "q"]).y.mean().unstack()
h = q.index < CUT
print("\nКвинтили ОСТАТКА доли канала (то, что не объясняется ценой и фандингом), доход лонга за неделю, %:")
print("   " + "  ".join(f"Q{i}: {q[i].mean()*100:+.2f}" for i in range(5)))
sp = q[0] - q[4]
print(f"   Q0−Q4 {sp.mean()*100:+.2f}%/нед (t {sp.mean()/sp.std()*np.sqrt(len(sp)):.2f}, 1-я/2-я {sp[h].mean()*100:+.2f}/{sp[~h].mean()*100:+.2f})")
F.to_pickle("s10/factor5b.pkl")
