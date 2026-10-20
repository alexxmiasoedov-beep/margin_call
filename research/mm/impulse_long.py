"""Лонг после «новостной» свечи: 15-мин свеча ≥ +10%, закрытие в верхней четверти, объём ≥ 10× медианы суток, 8 ч до неё — размах ≤ 10%.
Вход — закрытие свечи (+ проскальзывание 0,3%). Выходы — разные тейки/стопы/удержание. Комиссии 0,1%, фандинг не учтён (часы)."""
import pickle, datetime, sys
import numpy as np, pandas as pd
MSK = datetime.timezone(datetime.timedelta(hours=3))
K = pickle.load(open("kaia/k15_6m.pkl", "rb"))
P = {"месяц 19.09–18.10": (datetime.datetime(2026, 9, 19, tzinfo=MSK).timestamp(), datetime.datetime(2026, 10, 18, tzinfo=MSK).timestamp()),
     "полгода до него 18.03–18.09": (datetime.datetime(2026, 4, 8, tzinfo=MSK).timestamp(), datetime.datetime(2026, 9, 19, tzinfo=MSK).timestamp())}
ev = []
for s, k in K.items():
    t, o, h, l, c, v, qv = (k[:, j] for j in range(7)); last = -1e18
    for i in range(96 * 2, len(k) - 49):
        if t[i] - last < 86400: continue
        if c[i] / o[i] - 1 < 0.10 or (h[i] - c[i]) > 0.25 * (h[i] - l[i]): continue
        if h[i - 32:i].max() / l[i - 32:i].min() > 1.10: continue
        med = np.median(qv[i - 96:i])
        if med <= 0 or qv[i] < 10 * med: continue
        ev.append((s, i, t[i] + 900, c[i] / o[i] - 1)); last = t[i]
def trade(s, i, tp, sl, hold):
    k = K[s]; h, l, c = k[:, 2], k[:, 3], k[:, 4]; p = c[i] * 1.003
    for d in range(1, hold + 1):
        if i + d >= len(k): return np.nan
        if l[i + d] <= p * (1 - sl): return -sl - 0.001
        if h[i + d] >= p * (1 + tp): return tp - 0.001
    return c[i + hold] / p - 1 - 0.001
V = [(0.15, 0.10, 16), (0.20, 0.10, 32), (0.10, 0.07, 8), (0.30, 0.15, 48), (None, 0.15, 8), (None, 0.20, 16)]
for pname, (a, b) in P.items():
    E = [e for e in ev if a <= e[2] <= b]
    print(f"\n{pname}: новостных свечей {len(E)} у {len({e[0] for e in E})} монет, медиана свечи +{np.median([e[3] for e in E])*100:.0f}%")
    for tp, sl, hold in V:
        r = np.array([trade(s, i, tp if tp else 9.9, sl, hold) for s, i, _, _ in E]); r = r[np.isfinite(r)]
        lab = f"тейк {int(tp*100)}% / стоп {int(sl*100)}% / {hold//4} ч" if tp else f"без тейка / стоп {int(sl*100)}% / {hold//4} ч"
        print(f"  {lab:28s} сделок {len(r)} | {r.mean()*100:+.2f}% на сделку (медиана {np.median(r)*100:+.1f}%), в плюсе {np.mean(r > 0)*100:.0f}%")
pickle.dump(ev, open("mm/impulse_events.pkl", "wb"))
