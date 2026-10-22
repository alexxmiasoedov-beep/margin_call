"""Сетка параметров на «лесенке» — вход каждый день 1/7 капитала на 7 дней (средний ряд по 7 дням входа),
выбор на 1-й половине, проверка на 2-й. t по Ньюи–Уэсту (лаг 1)."""
import datetime, itertools
import numpy as np, pandas as pd
exec(open("s10/factor8.py").read().split("print(\"1)")[0])
D["wk"] = ((D["T"] - D["T"].min()) // (7 * 86400)).astype(int)
def ladder(look=7, N=10, vmin=10e6, fcut=-0.001, hedge="market", h=7):
    w = series(D, look, N, vmin, None if fcut == "нет" else fcut, None if hedge == "нет" else hedge, h)
    wk = ((w.index - D["T"].min()) // (7 * 86400)).astype(int)
    s = w.groupby(wk).mean(); s.index = D.groupby("wk")["T"].min().reindex(s.index).values
    return s
def nw_t(w, lag=1):
    x = w.values - w.mean(); n = len(x); g0 = (x @ x) / n
    g = sum((1 - l / (lag + 1)) * 2 * (x[l:] @ x[:-l]) / n for l in range(1, lag + 1))
    return w.mean() / np.sqrt((g0 + g) / n)
def st2(w):
    w = w.dropna(); h = w.index < CUT; eq = w.cumsum()
    return dict(m=w.mean(), t=nw_t(w), m1=w[h].mean(), t1=nw_t(w[h]), m2=w[~h].mean(), t2=nw_t(w[~h]), dd=(eq - eq.cummax()).min(), pos=(w > 0).mean())
base = ladder()
r = st2(base)
print(f"Базовый вариант лесенкой (окно 7, топ-10, ≥10 млн, фильтр −0,1%, лонг рынка): {r['m']*100:+.2f}%/нед (t {r['t']:.2f}; 1-я {r['m1']*100:+.2f} t {r['t1']:.2f} / "
      f"2-я {r['m2']*100:+.2f} t {r['t2']:.2f}; просадка {r['dd']*100:.1f}%; недель в плюсе {r['pos']:.0%})")
for hedge in ("margin", "нет"):
    r = st2(ladder(hedge=hedge))
    print(f"   хедж {hedge:6s}: {r['m']*100:+.2f}%/нед (t {r['t']:.2f}; 1-я {r['m1']*100:+.2f} / 2-я {r['m2']*100:+.2f}; просадка {r['dd']*100:.1f}%)")
res = []
for look, N, vmin, fcut, hedge in itertools.product((3, 7, 14), (5, 10, 20), (3e6, 10e6, 20e6), ("нет", -0.0005, -0.001, -0.002), ("market", "margin", "нет")):
    r = st2(ladder(look, N, vmin, fcut, hedge)); r.update(look=look, N=N, vmin=vmin, fcut=str(fcut), hedge=hedge); res.append(r)
R = pd.DataFrame(res); R.to_pickle("s10/factor8b_grid.pkl")
print(f"\nвариантов {len(R)}; в плюсе на 2-й половине {(R.m2 > 0).mean():.0%}; t₂ > 2 у {(R.t2 > 2).mean():.0%}; медиана 2-й {R.m2.median()*100:+.2f}%/нед")
for hedge in ("market", "margin", "нет"):
    q = R[R.hedge == hedge]; b = q.sort_values("t1", ascending=False).iloc[0]
    print(f"   хедж {hedge:6s}: лучший на 1-й — окно {b.look}, топ-{b.N}, ≥ {b.vmin/1e6:.0f} млн, фандинг {b.fcut}: 1-я {b.m1*100:+.2f} (t {b.t1:.2f}) → 2-я {b.m2*100:+.2f} (t {b.t2:.2f}) | "
          f"по всем вариантам с этим хеджем: 2-я в плюсе {(q.m2 > 0).mean():.0%}, медиана {q.m2.median()*100:+.2f}")
print("\nМедиана дохода на 2-й половине по значениям параметра (по всем остальным), %/нед:")
for c in ("look", "N", "vmin", "fcut", "hedge"):
    print(f"   {c:6s} " + "  ".join(f"{k}: {v*100:+.2f}" for k, v in R.groupby(R[c].astype(str)).m2.median().items()))
print("\nКорреляция ранга вариантов 1-я ↔ 2-я половина (Спирмен):", round(R.m1.rank().corr(R.m2.rank()), 2))
