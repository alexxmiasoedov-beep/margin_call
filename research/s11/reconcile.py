"""Сверка с серверным прогоном (tools/margin_rate_history.py): тот же период (с 27.09.2025), понедельники, объём ≥ 10 млн,
ставка = средняя за 7 суток, доход — только цена (без фандинга). Затем то же с фандингом — сколько съедает фандинг."""
import datetime
import numpy as np, pandas as pd
P = pd.read_pickle("s11/panel2.pkl")
UTC = datetime.timezone.utc
t0 = datetime.datetime(2025, 9, 29, 1, tzinfo=UTC).timestamp()
x = P[(P["T"] >= t0) & (P.v >= 10e6) & P.ret7.notna() & P.rate7.notna()].copy()
x["wd"] = pd.to_datetime(x["T"], unit="s").dt.weekday
mid = datetime.datetime(2026, 4, 9, tzinfo=UTC).timestamp()
def qtab(g, ycol):
    g = g.copy(); g["q"] = g.groupby("T").rate7.transform(lambda v: pd.qcut(v.rank(method="first"), 5, labels=False) if len(v) >= 25 else np.nan)
    q = g.dropna(subset=["q"]).groupby(["T", "q"])[ycol].mean().unstack(); sp = q[0] - q[4]; h = sp.index < mid
    return " ".join(f"Q{i+1} {q[i].mean()*100:+.2f}" for i in range(5)) + f" | Q1−Q5 {sp.mean()*100:+.2f} (t {sp.mean()/sp.std()*np.sqrt(len(sp)):.2f}; 1-я {sp[h].mean()*100:+.2f} / 2-я {sp[~h].mean()*100:+.2f}; недель {len(sp)})"
m = x[x.wd == 0]
print("понедельники, только цена:      ", qtab(m, "ret7"))
m = m.assign(y=m.ret7 - m.fr7)
print("понедельники, цена + фандинг:   ", qtab(m, "y"))
print("фандинг за неделю по квинтилям ставки (для лонга, %): ", end="")
m["q"] = m.groupby("T").rate7.transform(lambda v: pd.qcut(v.rank(method="first"), 5, labels=False))
print(" ".join(f"Q{int(i)+1} {-v*100:+.2f}" for i, v in m.groupby("q").fr7.mean().items()))
a = x.assign(y=x.ret7 - x.fr7)
print("все дни (лесенка), только цена: ", qtab(a, "ret7"))
print("все дни (лесенка), с фандингом: ", qtab(a, "y"))
P2 = P[(P.v >= 10e6) & P.ret7.notna() & P.rate7.notna()]
print("весь период 11.2024–10.2026, все дни, только цена:", qtab(P2, "ret7"))
