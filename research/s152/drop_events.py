"""s152 — события «час резкого падения к BTC» у ликвидных альтов (только частота, до гипотезы о доходе). Ежедневно —
30 самых торгуемых перпов за прошлые 30 сут (без BTC, ETH, стейблкоинов; перп старше 30 сут). Час H: ход монеты минус ход BTC
(закрытие к закрытию часовых свечей из 15-мин) ≤ порога; по монете не чаще раза в 4 ч. Запуск в папке периода с MC_K/MC_F."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s135"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live  # noqa: E402
import reset_test as R  # noqa: E402

DAY, H1 = 86400, 3600
SKIP = R.SKIP | {"BTC", "ETH"}


def hourly_all():
    H = {s: R.hourly(K[s]) for s in K if s not in SKIP or s == "BTC"}
    return H


def universe(H, t0, t1):
    """{сутки (начало, с): множество монет топ-30 по обороту за прошлые 30 сут}."""
    days = np.arange(t0 - t0 % DAY, t1, DAY)
    qv = {}
    for s, a in H.items():
        if s == "BTC":
            continue
        lo, hi = live(s)
        if not np.isfinite(lo):
            continue
        cs = np.r_[0.0, np.cumsum(a["qv"])]
        i1 = np.searchsorted(a["t"], days); i0 = np.searchsorted(a["t"], days - 30 * DAY)
        v = cs[i1] - cs[i0]
        v[(days - 30 * DAY < lo) | (days > hi)] = 0
        qv[s] = v
    S = list(qv); M = np.vstack([qv[s] for s in S])
    top = {}
    for k, d in enumerate(days):
        col = M[:, k]; idx = np.argsort(-col)[:30]
        top[int(d)] = {S[j] for j in idx if col[j] > 0}
    return top


def events(H, top, t0, t1, thr):
    b = H["BTC"]; bt = {int(t): c for t, c in zip(b["t"], b["c"])}
    out = []
    for s, a in H.items():
        if s == "BTC":
            continue
        t, c = a["t"], a["c"]; last = -10 ** 18
        for i in range(1, len(t)):
            T = int(t[i])
            if not (t0 <= T < t1) or T - last < 4 * H1 or a["qv"][i] <= 0:
                continue
            if s not in top.get(T - T % DAY, ()):
                continue
            b0, b1 = bt.get(T - H1), bt.get(T)
            if b0 is None or b1 is None or t[i - 1] != T - H1:
                continue
            rel = (c[i] / c[i - 1] - 1) - (b1 / b0 - 1)
            if rel <= thr:
                out.append((s, T + H1, rel)); last = T
    return out


if __name__ == "__main__":
    per, t0, t1 = sys.argv[1], int(pd.Timestamp(sys.argv[2], tz="UTC").timestamp()), int(pd.Timestamp(sys.argv[3], tz="UTC").timestamp())
    H = hourly_all(); top = universe(H, t0, t1)
    months = (t1 - t0) / (30.4 * DAY)
    for thr in (-0.01, -0.02, -0.03, -0.05):
        e = events(H, top, t0, t1, thr)
        print(f"{per} порог {thr:+.0%}: {len(e)} событий, {len(e) / months:.0f} в месяц", flush=True)
