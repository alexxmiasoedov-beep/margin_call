"""Импульсы месяца: 15-мин свеча закрылась ≥ +4% к предыдущей, а до неё 2 ч цена была в пределах ±5%. Момент — закрытие импульсной свечи."""
import pickle, datetime
import numpy as np
K = pickle.load(open("kaia/k15_all.pkl", "rb"))
MSK = datetime.timezone(datetime.timedelta(hours=3))
T0 = datetime.datetime(2026, 9, 19, tzinfo=MSK).timestamp(); T1 = datetime.datetime(2026, 10, 18, tzinfo=MSK).timestamp()
ev = []
for s, k in K.items():
    c = k[:, 4]
    for i in range(10, len(k) - 25):
        if T0 <= k[i, 0] + 900 <= T1 and c[i] / c[i - 1] - 1 >= 0.04 and abs(c[i - 1] / c[i - 9] - 1) <= 0.05:
            if ev and ev[-1][1] == s and i - ev[-1][2] <= 8: continue
            ev.append(("imp", s, i))
print("импульсов", len(ev), "у", len({s for _, s, _ in ev}), "монет")
pickle.dump(ev, open("mm2/imp_mom.pkl", "wb"))
