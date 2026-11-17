"""s128 — шорт пампов по фандингу в момент пампа (гипотеза — ВЫВОДЫ.md, записана до расчёта). Пампы — s15/kr_panel.pumps на архиве
MC_K/MC_F, одна сделка на монету за 48 ч; ставка — последнее начисление до закрытия свечи пампа; шорт 10/25/48
(s15/common.trade). Итог — s128_<метка>.pkl. Запуск: python3 <repo>/research/s128/fund_pump.py <метка>"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s105"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, funding, trade  # noqa: E402
from kr_panel import pumps  # noqa: E402
from jumps_test import SKIP  # noqa: E402


def main():
    lab = sys.argv[1]
    rows = []
    for s in K:
        if s in SKIP:
            continue
        pj = pumps(K[s])
        if not len(pj):
            continue
        fr = funding(s); last = -1e18
        for j in pj:
            T = float(K[s]["t"][j] + 900)
            if T - last < 48 * 3600:
                continue
            f = fr[fr[:, 0] <= T] if len(fr) else fr
            if not len(f):
                continue
            x = trade(s, int(j), tp=0.10, sl=0.25, hold_h=48)
            if not x:
                continue
            last = T
            rows.append(dict(s=s, t=T, rate=float(f[-1, 1]), net=x["net"]))
    X = pd.DataFrame(rows)
    X.to_pickle(f"s128_{lab}.pkl")
    print(lab, "пампов", len(X))


if __name__ == "__main__":
    main()
