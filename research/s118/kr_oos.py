"""s118 — 🇰🇷 вне выборки 10.2022–09.2024: памп +15% за ≤ 2 ч из покоя (s15/kr_panel.pumps), доля Upbit + Bithumb в обороте
последнего часа (s15/kr_panel.pkl, колонка share, построена s118/kr_build_oos.py) ≥ 20% → шорт 10/25/48 на закрытии свечи
пампа, одна сделка на монету за 24 ч; плацебо — та же монета за 45/90/135 сут. Запуск из ~/mc_oos после kr_panel.py:
MC_K=… MC_F=… MC_CUT=2023-10-01 python3 <repo>/research/s118/kr_oos.py"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

EX = dict(tp=0.10, sl=0.25, hold_h=48)


def main():
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb")); KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    rows = []
    for s, pj in PU.items():
        kp = KP.get(s)
        if kp is None or not len(pj):
            continue
        Tv = kp["T"].values; sh = kp["share"].values
        last = -1e18
        for j in pj:
            Tp = int(K[s]["t"][j]) + 900
            k = int(np.searchsorted(Tv, Tp, side="right")) - 1
            if k < 0 or Tp - Tv[k] >= 3600:
                continue
            share = float(sh[k])
            if Tp - last < 24 * 3600:
                continue
            x = trade(s, j, **EX)
            if x is None:
                continue
            last = Tp
            p = [y["net"] for dd in (45, 90, 135) if j - dd * 96 >= 96 and (y := trade(s, j - dd * 96, **EX))]
            rows.append(dict(s=s, t=Tp, kr=share, net=x["net"], pl=np.mean(p) if p else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle("s118_kr.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    for lab, x in (("доля Кореи ≥ 20% (🇰🇷)", X[X.kr >= 0.2]), ("доля Кореи < 20%", X[X.kr < 0.2]), ("все пампы монет с рынком к воне", X)):
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        h1, h2 = x[x.t < CUT], x[x.t >= CUT]
        print(f"  {lab:32s} n={n:4d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} | "
              f"половины {h1.net.mean():+6.2%} ({len(h1)}) / {h2.net.mean():+6.2%} ({len(h2)}) | плацебо {x.pl.mean():+6.2%}, "
              f"разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
