"""s109 — проверка пары s108 на второй половине (правило — ВЫВОДЫ.md, записано до проверки). Отбор — s108/pair_grid.pairs
(v = 1, w = 0) на всей панели; доход пары без стопа из панели и со стопом 20% на каждой ноге (s15/common.trade).
Плацебо — в те же дни случайная монета вселенной в лонг и случайная в шорт (20 розыгрышей). Запуск из папки с данными
после s108/long_map.py: python3 <repo>/research/s109/pair_test.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s108"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402
from pair_grid import X, pairs  # noqa: E402


def stopped(s, t, side):
    i = idx_at(s, t)
    r = trade(s, i, tp=None, sl=0.2, hold_h=168, side=side) if i is not None else None
    return r["net"] if r else np.nan


def main():
    P = pairs(X, 1.0, 0.0)
    P["rl20"] = [stopped(s, t, 1) for s, t in zip(P.long, P.t)]
    P["rs20"] = [stopped(s, t, -1) for s, t in zip(P.short, P.t)]
    P["pair20"] = P.rl20 + P.rs20
    rng = np.random.default_rng(7)
    pl = []
    for t, g in X.groupby("t"):
        n = (P.t == t).sum()
        if n == 0:
            continue
        for _ in range(20):
            a = g.sample(n, replace=True, random_state=int(rng.integers(1 << 31)))
            b = g.sample(n, replace=True, random_state=int(rng.integers(1 << 31)))
            pl.append((t, float(np.mean(a.L7.values + b.S7.values))))
    PL = pd.DataFrame(pl, columns=["t", "pl"]).groupby("t").pl.mean()
    P["pl"] = P.t.map(PL)
    P.to_pickle("s109/pairs.pkl")
    for lab, x in (("1-я половина (подбор)", P[P.t + 7 * DAY < CUT]), ("2-я половина (проверка)", P[P.t >= CUT]), ("вся история", P)):
        months = (x.t.max() - x.t.min()) / (30.4 * DAY)
        m, t, n = ct(x.pair, x.t); dp, tp, _ = ct(x.pair - x.pl, x.t)
        m20, t20, _ = ct(x.pair20, x.t)
        print(f"{lab:24s} пар {n:4d} ({n / months:5.1f}/мес) пара {m:+.2%} (t {t:+.1f}) в плюсе {(x.pair > 0).mean():.0%} | "
              f"лонг-нога {x.rl.mean():+.2%} (t {ct(x.rl, x.t)[1]:+.1f}), шорт-нога {x.rs.mean():+.2%} (t {ct(x.rs, x.t)[1]:+.1f}) | "
              f"плацебо {x.pl.mean():+.2%}, разница {dp:+.2%} (t {tp:+.1f}) | со стопами 20% {m20:+.2%} (t {t20:+.1f})")
    q = P[P.t >= CUT].copy(); q["m"] = pd.to_datetime(q.t, unit="s").dt.to_period("Q")
    print("2-я половина по кварталам:", " | ".join(f"{k}: {g.pair.mean():+.2%} ({len(g)})" for k, g in q.groupby("m")))


if __name__ == "__main__":
    main()
