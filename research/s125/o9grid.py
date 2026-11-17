"""s125 — расширение ⏰ (протокол — ВЫВОДЫ.md, записан до расчёта): события в 01:00 UTC из s15/kr_panel.pkl рабочей папки
с r1 ≥ 3% и share ≥ 10% (шорт 10/25/48, s15/common.trade; плацебо — та же монета за 45/90/135 сут), раз в сутки на монету.
Итог — s125_<метка>.pkl. Запуск: python3 <repo>/research/s125/o9grid.py <метка>"""
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

EX = dict(tp=0.10, sl=0.25, hold_h=48)


def main():
    lab = sys.argv[1]
    KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    rows = []
    for s, d in KP.items():
        lo, hi = live(s)
        x = d[(d["T"] % DAY == 3600) & (d.r1 >= 0.03) & (d.share >= 0.10) & (d["T"] >= lo + DAY) & (d["T"] <= hi - 3 * DAY)]
        for T, j, r1, sh in zip(x["T"].values, x.j.values, x.r1.values, x.share.values):
            T = int(T)
            y = trade(s, int(j), **EX)
            if not y:
                continue
            p = [z["net"] for dd in (45, 90, 135) if (k := idx_at(s, T - dd * DAY)) is not None and (z := trade(s, k, **EX))]
            rows.append(dict(s=s, t=float(T), r1=float(r1), share=float(sh), net=y["net"], pl=np.mean(p) if p else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"s125_{lab}.pkl")
    print(lab, "событий", len(X))


if __name__ == "__main__":
    main()
