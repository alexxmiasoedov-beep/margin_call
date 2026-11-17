"""s117 — 🌊 «отлив после фандинга» вне выборки: правило s23/g19_rule.py без изменений (начисление со ставкой ≤ −1%
при интервале ≥ 4 ч, шорт по закрытию 15-мин свечи T + 15 мин, выход T + 2 ч 15 мин, следующее начисление не раньше
чем через 30 мин после выхода; стоп 15% с проскальзыванием 0,2%, комиссия 0,1%). Архив — через MC_K/MC_F (s15/common).
Запуск: MC_K=… MC_F=… MC_CUT=2023-10-01 python3 <repo>/research/s117/fe_oos.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import FU, K  # noqa: E402
from oi_test import CUT, ct  # noqa: E402


def short(cl, hi, op, i, j, sl):
    p0 = cl[i]
    k = np.flatnonzero(hi[i + 1:j + 1] >= p0 * (1 + sl))
    if len(k):
        return 1 - max(p0 * (1 + sl), op[i + 1 + k[0]]) * 1.002 / p0 - 0.001
    return 1 - cl[j] / p0 - 0.001


rows = []
for s, f in FU.items():
    if s not in K or f is None or len(f) < 3:
        continue
    f = np.asarray(f, float); f = f[np.argsort(f[:, 0])]
    a = K[s]; t = a["t"].astype(np.int64); cl, hi, op = (a[x].astype(np.float64) for x in ("c", "h", "o")); lv = a["qv"] > 0
    for n in range(1, len(f) - 1):
        tf, ih, rate = f[n]
        if rate > -0.01 or f[n, 0] - f[n - 1, 0] < 4 * 3600 - 100:
            continue
        i = int(np.searchsorted(t, tf)); j = i + 8
        if i < 1 or j >= len(t) or t[i] != tf or not lv[i:j + 1].all() or f[n + 1, 0] < t[j] + 1800:
            continue
        rows.append(dict(s=s, T=float(tf), rate=rate, net=short(cl, hi, op, i, j, 0.15)))
R = pd.DataFrame(rows)
months = (R["T"].max() - R["T"].min()) / (30.4 * 86400)
m, tt, nn = ct(R.net, R["T"])
h1, h2 = R[R["T"] < CUT], R[R["T"] >= CUT]
print(f"🌊 вне выборки: сделок {nn} ({nn / months:.1f} в мес.), {m:+.2%} (t {tt:+.1f}), в плюсе {(R.net > 0).mean():.0%}; "
      f"половины {h1.net.mean():+.2%} ({len(h1)}) / {h2.net.mean():+.2%} ({len(h2)})")
q = pd.to_datetime(R["T"], unit="s").dt.to_period("Q")
print("по кварталам: " + " ".join(f"{k}:{g.net.mean():+.2%}({len(g)})" for k, g in R.groupby(q)))
R.to_pickle("s117/fe_oos.pkl")
