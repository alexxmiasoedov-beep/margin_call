"""Дополнения к фактору займа: (1) хедж одним BTC вместо корзины рынка; (2) ончейн — изменение балансов кошельков Binance
по токену за 7 дней (DefiLlama) как фильтр шортов; лесенка по всем дням входа."""
import datetime, re
import numpy as np, pandas as pd
exec(open("s10/factor8b.py").read().split("base = ladder()")[0])
D["y7"] = D.ret7 - D.fr7
btc = D[D.s == "BTC"].set_index("T").y7
print("BTC в панели:", len(btc), "дней")
def lad(w):
    wk = ((w.index - D["T"].min()) // (7 * 86400)).astype(int); s = w.groupby(wk).mean()
    s.index = D.groupby("wk")["T"].min().reindex(s.index).values; return s
def show(nm, w):
    r = st2(lad(w)); print(f"{nm:64s} {r['m']*100:+.2f}%/нед (t {r['t']:.2f}; 1-я {r['m1']*100:+.2f} / 2-я {r['m2']*100:+.2f}; просадка {r['dd']*100:.1f}%; в плюсе {r['pos']:.0%})")
d = D[(D.v >= 10e6) & D.ret7.notna()].copy()
pool = d[(d.sh7 > 0) & ~(d.f0 < -0.001)]
top = pool.assign(rr=pool.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= 10")
S = -top.groupby("T").y7.mean() - 0.001
show("шорт топ-10 (без хеджа)", S)
show("шорт топ-10 + лонг рынка поровну", (S + d.groupby("T").y7.mean().reindex(S.index) - 0.001) / 2)
show("шорт топ-10 + лонг BTC", (S + btc.reindex(S.index) - 0.001) / 2)
beta = np.polyfit(btc.reindex(S.index).fillna(0), -S, 1)[0]
print(f"   бета шорт-корзины к BTC (по 7-дн. доходностям): {beta:.2f}")
show(f"шорт топ-10 + лонг BTC на {beta:.1f}× объёма шортов", (S + beta * (btc.reindex(S.index) - 0.001)) / (1 + beta))
eth = D[D.s == "ETH"].set_index("T").y7
show("шорт топ-10 + лонг ETH", (S + eth.reindex(S.index) - 0.001) / 2)
# Ончейн: изменение балансов Binance по токену
Q = pd.read_pickle("s10/cex_qty.pkl")
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
dates = pd.to_datetime(d["T"], unit="s").dt.normalize()
def dq(s, dt):
    c = strip(s)
    if c not in Q.columns: return np.nan
    a, b = dt - pd.Timedelta(days=9), dt - pd.Timedelta(days=2)
    x0, x1 = Q[c].get(a, np.nan), Q[c].get(b, np.nan)
    return x1 / x0 - 1 if x0 and x0 > 0 and np.isfinite(x1) else np.nan
d["dq"] = [dq(s, t) for s, t in zip(d.s, dates)]
tp = d.loc[top.index]
cov = tp.dq.notna().groupby(tp["T"]).mean()
print(f"\nОнчейн-данные есть у {tp.dq.notna().mean():.0%} позиций топ-10 (до 01.12.2025: {cov[cov.index < CUT].mean():.0%}, после: {cov[cov.index >= CUT].mean():.0%})")
tp = tp[tp.dq.notna()]
tp["g"] = pd.cut(tp.dq, [-np.inf, -0.05, -0.01, 0.01, 0.05, np.inf], labels=["отток >5%", "отток 1–5%", "±1%", "приток 1–5%", "приток >5%"])
print("Доход шорта (7 дн, с фандингом, без комиссии) по изменению баланса Binance за неделю до входа:")
for g, x in tp.groupby("g", observed=True):
    y = -x.y7; h = x["T"] < CUT
    print(f"   {g:12s} {y.mean()*100:+.2f}% (медиана {y.median()*100:+.2f}%, позиций {len(x)}, 1-я/2-я {y[h].mean()*100:+.2f}/{y[~h].mean()*100:+.2f})")
# сравнение с корзиной без фильтра на тех же днях, где фильтр что-то меняет
alt = d[d.dq.notna()]
p2 = alt[(alt.sh7 > 0) & ~(alt.f0 < -0.001)]
for nm, cond in [("без ончейн-фильтра", None), ("без шортов с оттоком > 1%", p2.dq >= -0.01), ("только с притоком > 1%", p2.dq > 0.01)]:
    pp = p2 if cond is None else p2[cond]
    tt = pp.assign(rr=pp.groupby("T").sh7.rank(ascending=False, method="first")).query("rr <= 10")
    S2 = -tt.groupby("T").y7.mean() - 0.001
    show(f"   монеты с ончейн-данными, топ-10 {nm}", S2[S2.index >= CUT])
