"""s183 — Г1: сколько монет корзины «доля Кореи ≥ 15%, без журналов 7 сут» недавно получили рынок к воне (первые сутки
с оборотом к воне в кэше < 30 / < 90 сут до среза; в начале каждого периода возраст занижен — кэш начинается с периода).
Доходы не считаются. Запуск: python3 -I g1_age.py"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402
from coverage import load  # noqa: E402
from hyp_freq import KJ, recent_journal  # noqa: E402

for per in C.PERS:
    X = load(per)
    X = X[X.liq5.astype(bool)].replace([np.inf, -np.inf], np.nan).copy()
    J = C.journals(per)
    rj = recent_journal(J, KJ)
    X["kj7"] = [(d, s) in rj for d, s in zip(X.d0, X.s)]
    P = pd.read_pickle(f"{C.OUT}/daily_{per}.pkl")
    first = P[P.krv.fillna(0) > 0].groupby("s").d.min()
    t0 = C.ts(C.PER[per]["t0"])
    B = []
    for d0, g in X.groupby("d0"):
        g = g[(g.kshare7 >= 0.15) & ~g.kj7].sort_values("kshare7", ascending=False).head(5)
        B.append(g)
    B = pd.concat(B)
    B["kage"] = (B.d0 - B.s.map(first)) / C.DAY
    real = B.s.map(first) > t0 + 3 * C.DAY                 # рынок к воне открылся внутри периода
    print(f"{per}: монето-недель {len(B)}; рынок к воне открыт внутри периода у {real.mean():.0%}; "
          f"из них < 30 сут до среза — {(real & (B.kage < 30)).mean():.0%}, < 90 сут — {(real & (B.kage < 90)).mean():.0%}; "
          f"доля Кореи в корзине: медиана {B.kshare7.median():.0%}, p90 {B.kshare7.quantile(0.9):.0%}")
