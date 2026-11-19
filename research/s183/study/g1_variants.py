"""s183 — Г1: характеристики недельной корзины при порогах доли Кореи 15 / 20% (без входов корейских журналов за 7 сут)
и разрез «вето отрицательного фандинга» (f7 > −0,3% за 7 сут). Доходы не считаются. Запуск: python3 -I g1_variants.py"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402
from baskets import stats  # noqa: E402
from coverage import load  # noqa: E402
from hyp_freq import KJ, eligible, pick, recent_journal  # noqa: E402

for per in C.PERS:
    X = load(per)
    X = X[X.liq5.astype(bool)].replace([np.inf, -np.inf], np.nan).copy()
    J = C.journals(per)
    rj = recent_journal(J, KJ)
    X["kj7"] = [(d, s) in rj for d, s in zip(X.d0, X.s)]
    mons = C.months(per)
    print(f"=== {per}")
    for name, cond in (("доля ≥ 15%, без журналов", lambda g: (g.kshare7 >= 0.15) & ~g.kj7),
                       ("доля ≥ 15%, без журналов, f7 > −0,3%", lambda g: (g.kshare7 >= 0.15) & ~g.kj7 & (g.f7 > -0.003)),
                       ("доля ≥ 20%, без журналов", lambda g: (g.kshare7 >= 0.20) & ~g.kj7),
                       ("контроль: к воне, доля ≤ 3%", lambda g: (g.kshare7 <= 0.03) & g.kshare7.notna())):
        med, p10 = eligible(X, cond)
        B = pick(X, "kshare7", cond, asc=name.startswith("контроль"))
        st = stats(B, J, per, mons, X)
        print(f"  {name:38s} прошло/срез {med:5.1f} | сделок/мес {st['per_month']:5.1f} | полных {st['full']:4.0%} | замен {st['turnover']:4.0%} "
              f"| монет {st['coins']:4d} | топ-3 {st['top3']:4.0%} | журнал в неделю {st['any_now']:4.0%} | бета {st['beta']:.2f} "
              f"| σ нед. {st['sig_w']:.1%} | f7 {st['f7']:+.3%} | MDE {st['mde']:.2%} | {st['top_coins']}")
