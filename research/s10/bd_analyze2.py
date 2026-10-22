"""Биды на 3% к обороту как фильтр корзины: честно (порог по дню среди корзины или порог 1-й половины), отдельно аски,
отношение бидов к аскам — чтобы отличить «лимитный покупатель» от общей глубины стакана; перемешивание внутри дня."""
import datetime
import numpy as np, pandas as pd
exec(open("s10/bd_analyze.py").read().split("t = top[ok].copy()")[0])
t = top[ok].copy(); t["half"] = np.where(t["T"] < CUT, 1, 2)
t["bv"] = t.b3 / t.v; t["av"] = t.a3 / t.v; t["ba"] = t.b3 / t.a3
mk = d.groupby("T").y7.mean() - 0.001
def lad(w):
    wk = ((w.index - D["T"].min()) // (7 * 86400)).astype(int); s = w.groupby(wk).mean()
    s.index = D.groupby("wk")["T"].min().reindex(s.index).values; return s
def show(nm, x):
    S = x.groupby("T").sp.mean(); w = lad((S + mk.reindex(S.index)) / 2); h = w.index < CUT; eq = w.cumsum()
    print(f"   {nm:60s} {w.mean()*100:+.2f}%/нед (t {nw_t(w):.2f}; 1-я {w[h].mean()*100:+.2f} / 2-я {w[~h].mean()*100:+.2f}; просадка {(eq-eq.cummax()).min()*100:.1f}%; на позицию {x.sp.mean()*100:+.2f}%)")
    return w
print("Квартили внутри дня среди корзины (ранг по дню, без заглядывания вперёд), доход шорта на позицию, %:")
for col, nm in [("bv", "биды 3% / оборот"), ("av", "аски 3% / оборот"), ("ba", "биды / аски на 3%")]:
    t["q"] = t.groupby("T")[col].rank(pct=True)
    g = pd.cut(t.q, [0, 0.25, 0.5, 0.75, 1.0], labels=["Q1", "Q2", "Q3", "Q4"])
    r = t.groupby([g, "half"], observed=True).sp.mean().unstack() * 100; n = t.groupby(g, observed=True).sp.agg(["mean", "median"]) * 100
    print(f"   {nm:18s} " + "  ".join(f"{q}: {n.loc[q, 'mean']:+.2f} (мед {n.loc[q, 'median']:+.2f}; {r.loc[q, 1]:+.2f}/{r.loc[q, 2]:+.2f})" for q in ["Q1", "Q2", "Q3", "Q4"]))
print("\nЛесенка, шорт + рынок:")
base = show("вся корзина", t)
t["q"] = t.groupby("T").bv.rank(pct=True)
show("без четверти с самыми толстыми бидами (по дню)", t[t.q <= 0.75])
show("без трети с самыми толстыми бидами (по дню)", t[t.q <= 2 / 3])
thr = t[t.half == 1].bv.quantile(0.75)
show(f"порог 1-й половины: биды/оборот < {thr:.3f}", t[t.bv < thr])
t["qa"] = t.groupby("T").av.rank(pct=True)
show("для сравнения: без четверти с самыми толстыми АСКАМИ", t[t.qa <= 0.75])
# перемешивание: случайно выкидываем ту же долю позиций внутри дня
rng = np.random.default_rng(7); sims = []
for _ in range(200):
    rr = t.groupby("T").bv.transform(lambda x: pd.Series(rng.permutation(len(x)) / len(x), index=x.index))
    S = t[rr < 0.75].groupby("T").sp.mean(); sims.append(lad((S + mk.reindex(S.index)) / 2).mean())
sims = np.array(sims)
print(f"\n   перемешивание (выкидываем случайную четверть внутри дня, 200 раз): {sims.mean()*100:+.2f}%/нед, 95-й перцентиль {np.percentile(sims, 95)*100:+.2f}, максимум {sims.max()*100:+.2f}")
print("\nКорреляции внутри корзины (по рангам): биды/оборот с ...", ", ".join(f"{c}: {t[['bv', c]].rank().corr().iloc[0, 1]:+.2f}" for c in ["av", "v", "vol", "sh7", "r7", "f0"]))
