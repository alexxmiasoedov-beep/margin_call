"""Три группы моментов за 19.09–18.10 по всем фьючерсам (15 мин): ПАМП (+15% за ≤ 2 ч), ДАМП (−15% за ≤ 2 ч), ПОКОЙ (движение < 5%).
Во всех трёх за 2 ч до момента цена в пределах ±5%. Момент события — последняя спокойная свеча перед движением."""
import pickle, datetime, random
import numpy as np
random.seed(11)
MSK = datetime.timezone(datetime.timedelta(hours=3))
K = pickle.load(open("kaia/k15_all.pkl", "rb"))
T0 = datetime.datetime(2026, 9, 19, tzinfo=MSK).timestamp(); T1 = datetime.datetime(2026, 10, 18, tzinfo=MSK).timestamp()
E = {"памп": [], "дамп": [], "покой": []}
for s, k in K.items():
    t, h, l, c = k[:, 0], k[:, 2], k[:, 3], k[:, 4]
    idx = np.arange(96 * 2, len(k) - 8); te = t[idx] + 900
    ok = (te >= T0) & (te <= T1) & (np.abs(c[idx] / c[idx - 8] - 1) <= 0.05)
    up = np.array([h[i + 1:i + 9].max() / c[i] - 1 for i in idx]); dn = np.array([l[i + 1:i + 9].min() / c[i] - 1 for i in idx])
    for name, cond in (("памп", ok & (up >= 0.15) & (dn > -0.07)), ("дамп", ok & (dn <= -0.15) & (up < 0.07))):
        q = idx[cond]; grp = []
        for i in q:
            if grp and i - grp[-1][-1] <= 8: grp[-1].append(i)
            else: grp.append([i])
        E[name] += [(s, g[-1]) for g in grp]
    calm = idx[ok & (up < 0.05) & (dn > -0.05)]
    if len(calm): E["покой"] += [(s, int(i)) for i in random.sample(list(calm), min(3, len(calm)))]
for name, v in E.items(): print(f"{name}: {len(v)} моментов у {len({s for s, _ in v})} монет")
pickle.dump(E, open("mm2/events.pkl", "wb"))
