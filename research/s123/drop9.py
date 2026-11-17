"""s123 — зеркало ⏰ (гипотеза — ВЫВОДЫ.md, записана до расчёта): падение фьючерса ≥ 5% за час 00:00–01:00 UTC при доле Кореи
≥ 20% → лонг в 01:00 UTC 10/25/48 и 24 ч / стоп 15% (s15/common.trade); контроль — другие часы (раз в сутки на монету);
плацебо — та же монета за 45/90/135 сут. Данные — s15/kr_panel.pkl рабочей папки и архив MC_K/MC_F.
Итог — s123_<метка>.pkl. Запуск: python3 <repo>/research/s123/drop9.py <метка>"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import live, trade  # noqa: E402
from oi_test import DAY, idx_at  # noqa: E402

EX = {"L_10_25": dict(tp=0.10, sl=0.25, hold_h=48), "L_24h": dict(tp=None, sl=0.15, hold_h=24)}


def main():
    lab = sys.argv[1]
    KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    rows = []
    for s, d in KP.items():
        lo, hi = live(s)
        x = d[(d.r1 <= -0.05) & (d.share >= 0.20) & (d["T"] >= lo + DAY) & (d["T"] <= hi - 3 * DAY)]
        seen = set()
        for T, j, r1, sh in zip(x["T"].values, x.j.values, x.r1.values, x.share.values):
            T = int(T); day = T // DAY
            if day in seen:
                continue
            seen.add(day)
            r = dict(s=s, t=T, open9=T % DAY == 3600, r1=float(r1), share=float(sh))
            for nm, kw in EX.items():
                y = trade(s, int(j), side=1, **kw)
                r[nm] = y["net"] if y else np.nan
                p = [z["net"] for dd in (45, 90, 135) if (k := idx_at(s, T - dd * DAY)) is not None and (z := trade(s, k, side=1, **kw))]
                r["pl_" + nm] = np.mean(p) if p else np.nan
            rows.append(r)
    X = pd.DataFrame(rows)
    X.to_pickle(f"s123_{lab}.pkl")
    print(lab, "событий", len(X), "из них в 01:00 UTC", int(X.open9.sum()))


if __name__ == "__main__":
    main()
