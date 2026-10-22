"""Сочетание займа и цены внутри маржинальных монет: шорт топ-10 по сумме рангов (присутствие в канале + волатильность / рост за 7 дней),
лесенка по дням, хедж рынком. Сравнение с чистым займом и чистой ценой на той же панели."""
import datetime
import numpy as np, pandas as pd
exec(open("s10/factor8b.py").read().split("base = ladder()")[0])
d = D[(D.v >= 10e6) & D.ret7.notna()].copy(); d["y7"] = d.ret7 - d.fr7
mk = d.groupby("T").y7.mean() - 0.001
def lad(w):
    wk = ((w.index - D["T"].min()) // (7 * 86400)).astype(int); s = w.groupby(wk).mean()
    s.index = D.groupby("wk")["T"].min().reindex(s.index).values; return s
def run(nm, pool, score):
    pool = pool.assign(sc=score).dropna(subset=["sc"])
    top = pool.assign(rr=pool.groupby("T").sc.rank(ascending=False, method="first")).query("rr <= 10")
    S = -top.groupby("T").y7.mean() - 0.001
    w = lad((S + mk.reindex(S.index)) / 2); ws = lad(S); h = w.index < CUT; eq = w.cumsum()
    print(f"{nm:58s} шорт+рынок {w.mean()*100:+.2f}%/нед (t {nw_t(w):.2f}; 1-я {w[h].mean()*100:+.2f} / 2-я {w[~h].mean()*100:+.2f}; просадка {(eq-eq.cummax()).min()*100:.1f}%) | только шорт {ws.mean()*100:+.2f}")
ok = ~(d.f0 < -0.001)
mg = d[ok & d.seen90]
rk = lambda col: mg.groupby("T")[col].rank(pct=True)
run("маржинальные: присутствие в канале (как в базе)", mg[mg.sh7 > 0], mg[mg.sh7 > 0].sh7)
run("маржинальные: волатильность", mg, mg.vol)
run("маржинальные: рост за 7 дней", mg, mg.r7)
run("маржинальные: присутствие + волатильность (сумма рангов)", mg, rk("sh7") + rk("vol"))
run("маржинальные: присутствие + рост за 7 дней", mg, rk("sh7") + rk("r7"))
run("маржинальные: присутствие + волатильность + рост", mg, rk("sh7") + rk("vol") + rk("r7"))
