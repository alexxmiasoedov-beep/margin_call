"""s259 — частота события Г2 (для гипотез, доходы не считаются): у перпа без спота два начисления подряд r8 ≥ +0,05%, OI в монетах
за 24 ч +20% и больше, цена за 24 ч в пределах ±10%; первое у монеты за 24 ч. Покрытие OI — как cascade.py: полное (s228/met),
окна событий (s259/met), случайная выборка вне окон (s259/met_rand, вес пул / выборка).
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/g2_freq.py"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cascade import load_oi  # noqa: E402
from common259 import BAR, DAY, MID, OUT, T1, TMP, load_k  # noqa: E402


def events(s, F, oi, K, days=None):
    a = K[s]; t = a["t"].astype(np.int64) + BAR; c = a["c"].astype(float)
    g = F.get(s)
    if g is None or oi is None:
        return []
    ft, fr = g
    out, last = [], -1e18
    for k in range(1, len(ft)):
        T = int(ft[k])
        if fr[k] < 0.0005 or fr[k - 1] < 0.0005:
            continue
        if days is not None and (T // DAY * DAY) not in days:
            continue
        o1, o0 = oi.get(T // 3600 * 3600), oi.get(T // 3600 * 3600 - DAY)
        if o1 is None or o0 is None or not o0 > 0:
            continue
        i1 = np.searchsorted(t, T, side="right") - 1; i0 = np.searchsorted(t, T - DAY, side="right") - 1
        if i0 < 0 or i1 < 0:
            continue
        if o1 / o0 - 1 >= 0.20 and abs(c[i1] / c[i0] - 1) <= 0.10 and T - last >= DAY:
            out.append(T); last = T
    return out


def main():
    K = load_k()
    U = json.load(open(f"{OUT}/universe.json"))
    FP = pd.read_pickle(f"{TMP}/funding_panel.pkl")
    FP = FP[FP.ns]
    F = {s: (g.t.values, g.r8.values) for s, g in FP.groupby("s")}
    met228 = set(f[:-4] for f in os.listdir("s228/met"))
    win = json.load(open(f"{OUT}/met_days.json"))
    R = json.load(open(f"{OUT}/met_rand_days.json"))
    n_samp = sum(len(v) for v in R["days"].values()); wt = R["pool"] / n_samp
    cnt = {"full": [0, 0.0], "win": [0, 0.0], "rand": [0, 0.0]}
    late = {"full": 0, "win": 0, "rand": 0}
    for s, u in U.items():
        if s not in F:
            continue
        if s in met228:
            oi = load_oi(f"s228/met/{s}.npz")
            if oi is not None:
                e = events(s, F, oi.to_dict(), K)
                cnt["full"][0] += len(e); late["full"] += sum(x >= MID for x in e)
                cnt["full"][1] += len(F[s][0]) * 4 / 24 if len(F[s][0]) else 0         # монето-суток ≈ начислений · 4 ч / 24
        else:
            for src, path, dd in (("win", f"{OUT}/met/{s}.npz", win.get(s)), ("rand", f"{OUT}/met_rand/{s}.npz", R["days"].get(s))):
                if not dd:
                    continue
                oi = load_oi(path)
                if oi is None:
                    continue
                days = set(int(pd.Timestamp(x, tz="UTC").timestamp()) for x in dd)
                e = events(s, F, oi.to_dict(), K, days)
                cnt[src][0] += len(e); late[src] += sum(x >= MID for x in e)
                cnt[src][1] += len(days)
    tot2 = late["full"] + late["win"] + late["rand"] * wt
    mo2 = (T1 - MID) / (30.44 * DAY)
    print(f"Г2: полное покрытие {cnt['full'][0]} (2-я половина {late['full']}), окна {cnt['win'][0]} ({late['win']}), выборка "
          f"{cnt['rand'][0]} ({late['rand']}) × {wt:.1f}; оценка во 2-й половине по всем перпам без спота: {tot2 / mo2:.1f} в месяц")


if __name__ == "__main__":
    main()
