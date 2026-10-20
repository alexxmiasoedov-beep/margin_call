"""События за месяц (19.09–18.10) по 15-мин свечам всех фьючерсов:
ПАМП — из спокойного состояния (за 2 ч до старта цена в пределах ±5%) максимум следующих 2 ч ≥ +15% к цене старта;
РАЗВОРОТ — после роста ≥ +30% за 24 ч до вершины цена в следующие 24 ч падает ≥ 15% от вершины."""
import pickle, datetime
import numpy as np
MSK = datetime.timezone(datetime.timedelta(hours=3)); f = lambda t: datetime.datetime.fromtimestamp(t, MSK).strftime("%d.%m %H:%M")
K = pickle.load(open("kaia/k15_all.pkl", "rb"))
T0 = datetime.datetime(2026, 9, 19, tzinfo=MSK).timestamp(); T1 = datetime.datetime(2026, 10, 18, tzinfo=MSK).timestamp()
pumps, tops = [], []
for s, k in K.items():
    t, o, h, l, c, qv = k[:, 0], k[:, 1], k[:, 2], k[:, 3], k[:, 4], k[:, 6]
    last = -1e18
    for i in range(96 * 7, len(k) - 8):
        te = t[i] + 900                                          # момент старта — закрытие свечи i
        if te < T0 or te > T1 or te - last < 12 * 3600: continue
        if abs(c[i] / c[i - 8] - 1) > 0.05: continue              # 2 ч до старта — спокойно
        up = h[i + 1:i + 9].max() / c[i] - 1
        if up >= 0.15:
            j = i + 1 + int(np.argmax(h[i + 1:i + 9] >= c[i] * 1.15))
            pumps.append(dict(sym=s, i=i, t0=te, p0=c[i], up=up * 100, mins=(t[j] + 900 - te) / 60)); last = te
    last = -1e18
    for i in range(96, len(k) - 96):
        te = t[i] + 900
        if te < T0 or te > T1 or te - last < 24 * 3600: continue
        if h[i] < h[i - 96:i + 1].max() or h[i] / l[i - 96:i + 1].min() < 1.30: continue   # вершина суток после роста ≥ 30%
        if h[i] < h[i + 1:i + 5].max(): continue                                            # ещё час без нового максимума
        dn = l[i + 1:i + 97].min() / h[i] - 1
        tops.append(dict(sym=s, i=i, t0=te, top=h[i], dn=dn * 100, rev=dn <= -0.15)); last = te
pickle.dump(dict(pumps=pumps, tops=tops), open("mm/events.pkl", "wb"))
print(f"ПАМПЫ (+15% за ≤ 2 ч из спокойного состояния): {len(pumps)} событий у {len({p['sym'] for p in pumps})} монет; "
      f"медиана времени до +15%: {np.median([p['mins'] for p in pumps]):.0f} мин")
print(f"ВЕРШИНЫ после роста ≥ 30% за сутки: {len(tops)}; из них разворот с падением ≥ 15% за 24 ч: {sum(t['rev'] for t in tops)} "
      f"({np.mean([t['rev'] for t in tops])*100:.0f}%)")
k = [p for p in pumps if p["sym"] == "KAIA"]; print("KAIA в списке пампов:", [(f(p["t0"]), round(p["up"]), p["mins"]) for p in k])
