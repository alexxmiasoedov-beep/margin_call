"""s173 — частота H1 на профиле агрессивных покупок СПОТА (s23/spot1h, 10.2024–10.2026), без доходов.
Цена — закрытие спотового часа; ликвидность — оборот перпа за 24 ч ≥ 5 млн $. Также контрольная группа той же формы
с редкой зоной (плотность < 5%) — для оценки её размера. Запуск: python3 -I probe_h1_spot.py <папка данных>"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_freq import NONCRYPTO, hourly, month, roll_sum  # noqa: E402

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
with open(os.path.join(D, "s2/k2y.pkl"), "rb") as f:
    K = pickle.load(f)
kind = pd.read_pickle(os.path.join(D, "s12/perp_kind.pkl"))
BAD = set(kind.get("tradfi", set())) | NONCRYPTO
sp = pd.read_pickle(os.path.join(D, "s23/spot1h.pkl"))
lb = np.log(1.01)
rows = {"dense15": [], "dense20": [], "sparse": []}
for s in sp:
    if s in BAD or s not in K:
        continue
    T, x = hourly(K[s])
    a = np.asarray(sp[s])
    Hs = a[:, 0].astype(np.int64) // 3600
    m_ = (Hs >= T[0]) & (Hs <= T[-1])
    stb = np.zeros(len(T)); sc = np.full(len(T), np.nan)
    stb[(Hs[m_] - T[0]).astype(int)] = a[m_, 2]
    sc[(Hs[m_] - T[0]).astype(int)] = a[m_, 4]
    sc = pd.Series(sc).ffill().values
    good = np.isfinite(sc) & (sc > 0)
    if good.sum() < 24 * 40:
        continue
    b = np.full(len(T), np.nan); b[good] = np.floor(np.log(sc[good]) / lb)
    bmin = int(np.nanmin(b)) - 3; nb = int(np.nanmax(b)) - bmin + 5
    if nb > 2000:
        continue
    M = np.zeros((len(T), nb), np.float32)
    ii = np.flatnonzero(good)
    M[ii, (b[ii] - bmin).astype(int)] = stb[ii]
    C = np.cumsum(M, axis=0); del M
    v24 = roll_sum(x["qv"], 24)
    cs = pd.Series(sc)
    rise_ok = (cs / cs.shift(24) - 1).values >= 0.05
    prevmax = cs.shift(1).rolling(72, min_periods=72).max().values
    lower = 1.01 ** b
    first = np.flatnonzero(good)[0]
    cand = np.flatnonzero(good & (v24 >= 5e6) & rise_ok & (prevmax < lower))
    cand = cand[cand >= first + 720]
    last = {k: -10 ** 9 for k in rows}
    for i in cand:
        W = C[i - 72] - C[i - 720]; tot = W.sum()
        if tot <= 0:
            continue
        k0 = int(b[i] - bmin); dz = W[k0:k0 + 3].sum() / tot
        for key, ok in (("dense15", dz >= 0.15), ("dense20", dz >= 0.20), ("sparse", dz < 0.05)):
            if ok and i - last[key] >= 72:
                last[key] = i; rows[key].append(T[i])
for key, ts in rows.items():
    m = pd.Series([month(np.int64(t)) for t in ts]).value_counts().sort_index()
    full = m.iloc[1:-1]
    print(f"{key}: событий {len(ts)}, в месяц медиана {full.median():.0f}, среднее {full.mean():.0f}")
