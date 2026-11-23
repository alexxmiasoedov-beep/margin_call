"""s259, вопрос 1 (разрез) — error-correction 15 мин (как leadlag.py, |g| ≥ 0,5%) вне ±6 ч от пампов и обвалов и внутри них,
у перпов без спота и монет со спотом. Механика, не сделки.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/ecm_calm.py"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import OUT  # noqa: E402
from leadlag import block, prep  # noqa: E402
from premium import panel  # noqa: E402


def main():
    P = prep(panel())
    E = pd.read_pickle(f"{OUT}/events.pkl")
    ev = {s: np.sort(g.t.values) for s, g in E.groupby("p")}
    for s, d in P.items():
        t = d["t"]; x = ev.get(s, np.zeros(0))
        near = np.zeros(len(t), bool)
        if len(x):
            i = np.searchsorted(x, t)
            near = (np.abs(t - x[np.maximum(i - 1, 0)]) <= 6 * 3600) | (np.abs(x[np.minimum(i, len(x) - 1)] - t) <= 6 * 3600)
        d["near"] = near
    block(P, lambda s, d: d["ns"] & ~d["near"], "без спота, вне ±6 ч от пампов/обвалов", 0.005)
    block(P, lambda s, d: d["ns"] & d["near"], "без спота, в ±6 ч от пампов/обвалов", 0.005)
    block(P, lambda s, d: ~d["ns"] & ~d["near"], "со спотом, вне ±6 ч", 0.005)
    block(P, lambda s, d: ~d["ns"] & d["near"], "со спотом, в ±6 ч", 0.005)


if __name__ == "__main__":
    main()
