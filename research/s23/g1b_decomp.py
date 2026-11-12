"""Г1′ подробно, поиск на первой половине: доход окна R = λΦ (объяснён потоком по цене потока монеты) + D (не объяснён).
Регрессии на обе части; децили D; где эффект — рост/падение, ликвидность, окно 72 ч. Г3 — ветвление η (s23/eta.pkl).
Запуск из папки с данными."""
import pickle
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from feat23 import CUT, build, days, deciles, fm, fwd_ex, nw_t, report, universe

for W in (24, 72):
    F = build(W)
    F["FR"] = F["lam"] * F["PHI"]
    E = pickle.load(open("s23/eta.pkl", "rb"))
    for k in ("ETA3", "ETA30"):
        F[k] = E[k].reindex(index=F["C"].index, columns=F["C"].columns)
    F["dETA"] = F["ETA3"] - F["ETA30"]
    D = days(F); D = D[D < CUT]
    print(f"\n======== окно {W} ч, первая половина: срезов {len(D)}")
    for h in (24, 72, 168):
        Y = fwd_ex(F["C"], h)
        print(report(fm(F, Y, ["FR", "D"], D), h, "доход, объяснённый потоком (FR = λΦ), и необъяснённый (D)"))
        print(report(fm(F, Y, ["FR", "D", "VOL", "A", "TS"], D), h, "то же с контролем VOL, A, TS"))
        if W == 24:
            print(report(fm(F, Y, ["R", "ETA3"], D, extra=lambda X: {"R×ETA3": X["R"] * X["ETA3"] * 4}), h, "Г3: ветвление 3 сут"))
            print(report(fm(F, Y, ["R", "dETA"], D, extra=lambda X: {"R×dETA": X["R"] * X["dETA"] * 4}), h, "Г3: ветвление к норме монеты"))
        M = deciles(F, Y, "D", D)
        sp = M[9] - M[0]
        print(f"  децили D ({h // 24} сут), средний доход к рынку, %: " + " ".join(f"{v * 100:+.2f}" for v in M.mean())
              + f" | D10−D1 {sp.mean() * 100:+.2f}% (t {nw_t(sp, max(1, h // 24)):+.1f})")
        for nm, cond in (("рост R>0", lambda T, idx: F["R"].loc[T, idx] > 0), ("падение R<0", lambda T, idx: F["R"].loc[T, idx] < 0)):
            M = deciles(F, Y, "D", D, q=5, cond=cond)
            sp = M[4] - M[0]
            print(f"    квинтили D при {nm}: " + " ".join(f"{v * 100:+.2f}" for v in M.mean())
                  + f" | Q5−Q1 {sp.mean() * 100:+.2f}% (t {nw_t(sp, max(1, h // 24)):+.1f})")
        print(flush=True)
