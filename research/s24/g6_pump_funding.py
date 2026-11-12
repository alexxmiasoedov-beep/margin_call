"""Рост ≥ +25% к рынку за 24 ч (первый 4-часовой срез, не чаще раза в 3 суток на монету; s23/long4h.pkl) — шорт по
закрытию среза через common.trade: комиссия 0,1%, фактический фандинг, стоп 25%, 72 ч. По корзинам фандинга на 8 ч
в момент входа (F8) и по половинам. Запуск из папки с данными."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "/home/user/margin_call/research/s23")
from feat23 import CUT                                            # noqa: E402
from common23 import K, ct, trade                                # noqa: E402

L = pd.read_pickle("s23/long4h.pkl")
E = L[np.exp(L.R) - 1 >= 0.25].sort_values("T")
keep, last = [], {}
for i, (s, T) in enumerate(zip(E.s.values, E["T"].values)):
    if T - last.get(s, -1e18) >= 3 * 86400:
        keep.append(i); last[s] = T
E = E.iloc[keep].copy()


def bar(s, T):
    t = K[s]["t"]; i = int(np.searchsorted(t, T - 900))
    return i if i < len(t) and t[i] + 900 == T else None


rows = []
for r in E.itertuples():
    i = bar(r.s, r.T)
    if i is None:
        continue
    for sl in (0.25, 0.5):
        x = trade(r.s, i, tp=None, sl=sl, hold_h=72, side=-1)
        if x:
            rows.append(dict(s=r.s, T=r.T, F8=r.F8, sl=sl, net=x["net"], price=x["price"], fund=x["fund"], why=x["why"]))
R = pd.DataFrame(rows)
R["fb"] = pd.cut(R.F8 * 100, [-100, -0.1, -0.01, 0.005, 0.0101, 100], labels=["≤ −0,1%", "−0,1…−0,01%", "−0,01…0", "0…0,01%", "> 0,01%"])
for sl in (0.25, 0.5):
    print(f"\nшорт после роста ≥ 25% за сутки, стоп {sl:.0%}, 72 ч: по фандингу на 8 ч в момент входа")
    for b, g in R[R.sl == sl].groupby("fb", observed=True):
        m, t, n = ct(g.net.values, g["T"].values)
        print(f"  F8 {str(b):>12}: n={n:5d}, итог {m * 100:+.2f}% (t {t:+.1f}; половины {g.net[g['T'] < CUT].mean() * 100:+.2f} / "
              f"{g.net[g['T'] >= CUT].mean() * 100:+.2f}); цена {g.price.mean() * 100:+.2f}%, фандинг {g.fund.mean() * 100:+.2f}%; "
              f"стопов {(g.why == 'стоп').mean():.0%}")
