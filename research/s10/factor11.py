"""Состав корзины фактора займа: оборот, какие монеты, вклад отдельных монет, худшие недели, кварталы."""
import datetime
import numpy as np, pandas as pd
exec(open("s10/factor8b.py").read().split("base = ladder()")[0])
d = D[(D.v >= 10e6) & D.ret7.notna()].copy(); d["y7"] = d.ret7 - d.fr7
pool = d[(d.sh7 > 0) & ~(d.f0 < -0.001)]
top = pool.assign(rr=pool.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= 10").copy()
top["sp"] = -top.y7 - 0.001
sets = top.groupby("T").s.apply(set)
ov = [len(a & b) / 10 for a, b in zip(sets.values[:-1], sets.values[1:])]
ov7 = [len(a & b) / 10 for a, b in zip(sets.values[:-7], sets.values[7:])]
print(f"монет за всё время: {top.s.nunique()}; совпадение состава с вчерашним {np.mean(ov):.0%}, с неделей назад {np.mean(ov7):.0%}")
c = top.groupby("s").agg(n=("sp", "size"), m=("sp", "mean"), tot=("sp", "sum")).sort_values("n", ascending=False)
print("чаще всего в корзине (дней, средний доход шорта 7 дн):", "; ".join(f"{s} {r.n:.0f} ({r.m*100:+.1f}%)" for s, r in c.head(15).iterrows()))
c2 = c.sort_values("tot")
print("худшие по сумме:", "; ".join(f"{s} {r.tot*100:+.0f}% ({r.n:.0f} дн)" for s, r in c2.head(8).iterrows()))
print("лучшие по сумме:", "; ".join(f"{s} {r.tot*100:+.0f}% ({r.n:.0f} дн)" for s, r in c2.tail(8).iterrows()))
mk = d.groupby("T").y7.mean() - 0.001
def lad(w):
    wk = ((w.index - D["T"].min()) // (7 * 86400)).astype(int); s = w.groupby(wk).mean()
    s.index = D.groupby("wk")["T"].min().reindex(s.index).values; return s
for k in (0, 3, 5, 10):
    drop = set(c2.index[-k:]) if k else set()
    S = top[~top.s.isin(drop)].groupby("T").sp.mean()
    w = lad((S + mk.reindex(S.index)) / 2)
    print(f"без {k:2d} лучших монет: шорт+рынок {w.mean()*100:+.2f}%/нед (t {nw_t(w):.2f}); только шорт {lad(S).mean()*100:+.2f}%/нед")
S = top.groupby("T").sp.mean(); W = lad((S + mk.reindex(S.index)) / 2); Ws = lad(S)
print("\nхудшие недели (шорт+рынок | только шорт):")
for t in W.nsmallest(6).index:
    wk = top[(top["T"] >= t) & (top["T"] < t + 7 * 86400)]
    worst = wk.groupby("s").sp.mean().nsmallest(3)
    print(f"   {datetime.datetime.utcfromtimestamp(t):%d.%m.%Y}: {W[t]*100:+.1f}% | {Ws[t]*100:+.1f}%  — хуже всех: " + ", ".join(f"{s} {v*100:+.0f}%" for s, v in worst.items()))
q = W.groupby(pd.to_datetime(W.index, unit="s").to_period("Q")).agg(["sum", "size"])
qs = Ws.groupby(pd.to_datetime(Ws.index, unit="s").to_period("Q")).sum()
print("\nпо кварталам (сумма за квартал, %): " + "; ".join(f"{p}: {r['sum']*100:+.1f} | шорт {qs[p]*100:+.1f}" for p, r in q.iterrows()))
pd.DataFrame(dict(pair=W, short=Ws, mkt=lad(mk), btc=lad(D[D.s == 'BTC'].set_index('T').eval('ret7 - fr7')))).to_pickle("s10/factor11_weekly.pkl")
