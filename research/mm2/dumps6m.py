"""Дампы за 6,5 месяца (причинно): была спокойная свеча i в последние 2 ч, после неё минимум ушёл на −15% от её закрытия.
Вход — закрытие свечи, где это случилось впервые (одна на монету за 24 ч)."""
import pickle
import numpy as np
from pump_short6m import K
def detect(k, thr=0.15):
    c, l = k[:, 4], k[:, 3]; n = len(k); out = []; last = -10**9
    calm = np.zeros(n, bool); calm[8:] = np.abs(c[8:] / c[:-8] - 1) <= 0.05
    for j in range(9, n - 1):
        if j - last < 96: continue
        base = [i for i in range(max(8, j - 8), j) if calm[i] and l[i + 1:j + 1].min() <= c[i] * (1 - thr)]
        if base: out.append((j, base[-1])); last = j
    return out
EV = [(s, j, i) for s, k in K.items() if len(k) >= 200 for j, i in detect(k)]
pickle.dump(EV, open("mm2/dumps6m.pkl", "wb")); print("дампов", len(EV), "у", len({e[0] for e in EV}), "монет")
