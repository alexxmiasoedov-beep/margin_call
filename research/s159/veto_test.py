"""s159 — вето отрицательного фандинга для шорта пампов (гипотеза — ВЫВОДЫ.md, записана до расчёта). Пампы — s154_pumps_<период>.pkl;
ставка последнего начисления до входа, на 8 ч (s15/common.funding через MC_F). Запуск в папке периода с MC_K/MC_F:
python3 <repo>/research/s159/veto_test.py <период>; сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s157"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT = "/home/user/mc_data"
PER = ("2020–2022", "2022–2024", "2024–2026")


def run(per):
    from common import funding  # noqa: E402
    F = pd.read_pickle(f"{OUT}/s154_pumps_{per}.pkl")
    f8 = []
    for r in F.itertuples():
        fr = funding(r.s)
        if not len(fr):
            f8.append(np.nan); continue
        k = int(np.searchsorted(fr[:, 0], int(r.t), "right")) - 1
        if k < 1:
            f8.append(np.nan); continue
        iv = fr[k, 0] - fr[k - 1, 0]
        f8.append(float(fr[k, 1]) * 8 * 3600 / iv if 3600 - 60 <= iv <= 8 * 3600 + 60 else np.nan)
    F["f8"] = f8
    F.to_pickle(f"{OUT}/s159_{per}.pkl")
    print(per, len(F), "ставка ≤ −0,1%:", int((F.f8 <= -0.001).sum()))


def report():
    from opt_test import wdiff  # noqa: E402
    A = []
    for per in PER:
        F = pd.read_pickle(f"{OUT}/s159_{per}.pkl").rename(columns={"t": "te"}).dropna(subset=["f8"]); F["per"] = per; A.append(F)
        print(f"\n{per}:")
        for sub, X in (("все пампы", F), ("спот ≥ 26%", F[F.share >= 0.26])):
            for thr in (-0.001, -0.0005, 0.0):
                v, k = X[X.f8 <= thr], X[X.f8 > thr]; d, t = wdiff(k, v)
                print(f"  {sub:11s} вето ≤ {thr:+.2%}: оставлено {len(k)} {k.net.mean():+.2%}, под вето {len(v)} {v.net.mean():+.2%}, "
                      f"разница {d:+.2%} (t {t:+.1f})")
    A = pd.concat(A, ignore_index=True)
    for sub, X in (("все пампы", A), ("спот ≥ 26%", A[A.share >= 0.26])):
        v, k = X[X.f8 <= -0.001], X[X.f8 > -0.001]; d, t = wdiff(k, v)
        print(f"\nшесть лет, {sub}, вето ≤ −0,1%: оставлено {k.net.mean():+.2%}, под вето {v.net.mean():+.2%}, разница {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
