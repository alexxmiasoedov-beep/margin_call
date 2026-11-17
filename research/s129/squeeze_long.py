"""s129 — лонг сквиза (правило — ВЫВОДЫ.md, записано до расчёта): пампы s15/kr_panel.pumps при последнем начислении ≤ −0,01%,
одна сделка на монету за 48 ч; лонг 25/10/48 и 48 ч / стоп 15% (s15/common.trade, side=+1); плацебо — та же монета
за 45/90/135 сут. Итог — s129_<метка>.pkl. Запуск: python3 <repo>/research/s129/squeeze_long.py <метка>"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s105"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, funding, trade  # noqa: E402
from oi_test import DAY, idx_at  # noqa: E402
from kr_panel import pumps  # noqa: E402
from jumps_test import SKIP  # noqa: E402

EX = {"L25/10/48": dict(tp=0.25, sl=0.10, hold_h=48), "L48/S15": dict(tp=None, sl=0.15, hold_h=48)}


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
            if not len(f) or f[-1, 1] > -0.0001:
                continue
            d = dict(s=s, t=T, rate=float(f[-1, 1]))
            ok = True
            for nm, kw in EX.items():
                x = trade(s, int(j), side=1, **kw)
                if not x:
                    ok = False; break
                d[nm] = x["net"]; d["why_" + nm] = x["why"]
                p = [y["net"] for dd in (45, 90, 135) if (k := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, k, side=1, **kw))]
                d["pl_" + nm] = np.mean(p) if p else np.nan
            if ok:
                last = T
                rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle(f"s129_{lab}.pkl")
    print(lab, "сделок", len(X))


if __name__ == "__main__":
    main()
