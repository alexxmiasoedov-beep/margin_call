"""Простые идеи из литературы на наших данных: (1) лонг после дневной «капитуляции» (красная дневная свеча с объёмом
≥ m × среднего за 60 дней) — СНГ №4; (2) моментум среди крупных / разворот среди остальных — США №7, СНГ №3, Китай №7.
Фандинг и комиссия учтены, лесенка по дням (панель s11)."""
import sys, os, datetime
sys.path.insert(0, os.getcwd())
from s12.common import *
import pandas as pd
rows = []
for s, a in K.items():
    if s in TF or len(a["t"]) < 96 * 100: continue
    t = a["t"]; d0 = int((t[0] + 86399) // 86400 * 86400)
    j0 = int(np.searchsorted(t, d0)); n = (len(t) - j0) // 96
    if n < 90: continue
    o = a["o"][j0:j0 + n * 96].astype(float).reshape(n, 96); c = a["c"][j0:j0 + n * 96].astype(float).reshape(n, 96)
    qv = a["qv"][j0:j0 + n * 96].astype(float).reshape(n, 96).sum(1)
    do, dc = o[:, 0], c[:, -1]
    for i in range(60, n - 6):
        if dc[i] >= do[i] or qv[i] < 3e6: continue
        x = qv[i] / qv[i - 60:i].mean()
        if x < 2: continue
        T = d0 + (i + 1) * 86400
        for h in (1, 3, 5):
            r = dc[i + h] / dc[i] - 1
            rows.append(dict(s=s, T=T, m=x, h=h, lp=r - fsum(s, T, T + h * 86400) - 0.001, ret_d=dc[i] / do[i] - 1))
E = pd.DataFrame(rows)
print("(1) лонг после красной дневной свечи с объёмом ≥ m × 60-дн. среднего (вход на открытии следующего дня):")
for m_ in (2, 3, 4):
    for h in (1, 3, 5):
        g = E[(E.m >= m_) & (E.h == h)]; hh = g["T"] < CUT
        b = g[g.s.isin(["BTC", "ETH"])]
        print(f"   m ≥ {m_}, {h} сут: n {len(g):5d} лонг {g.lp.mean()*100:+.2f}% (медиана {g.lp.median()*100:+.2f}, в плюсе {(g.lp > 0).mean():.0%}; "
              f"1-я {g[hh].lp.mean()*100:+.2f} / 2-я {g[~hh].lp.mean()*100:+.2f}) | BTC+ETH n {len(b)} {b.lp.mean()*100:+.2f}%")
P = pd.read_pickle("s11/panel2.pkl"); P["y7"] = P.ret7 - P.fr7
d = P[(P.v >= 5e6) & P.ret7.notna()].copy()
d["big"] = d.groupby("T").v.transform(lambda x: x.rank(pct=True) >= 0.8)
def lad(w):
    wk = ((w.index - P["T"].min()) // (7 * 86400)).astype(int); s = w.groupby(wk).mean(); return s
print("\n(2) квинтили по доходности за 7 сут → доход лонга 7 сут с фандингом (лесенка), крупные (верх 20% по объёму) и остальные:")
for nm, g in (("крупные", d[d.big]), ("остальные", d[~d.big])):
    g = g.copy(); g["q"] = g.groupby("T").r7.transform(lambda x: pd.qcut(x.rank(method="first"), 5, labels=False) if len(x) >= 10 else np.nan)
    q = g.dropna(subset=["q"]).groupby(["T", "q"]).y7.mean().unstack(); sp = lad(q[4] - q[0]).dropna(); hh = sp.index < (CUT - P["T"].min()) // (7 * 86400)
    print(f"   {nm:9s} " + " ".join(f"Q{i+1} {lad(q[i]).mean()*100:+.2f}" for i in range(5)) +
          f" | моментум Q5−Q1 {sp.mean()*100:+.2f}%/нед (t {sp.mean()/sp.std()*np.sqrt(len(sp)):.2f}; 1-я {sp[hh].mean()*100:+.2f} / 2-я {sp[~hh].mean()*100:+.2f})")
