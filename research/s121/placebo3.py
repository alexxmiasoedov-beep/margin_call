"""s121 — плацебо (записано до расчёта, ВЫВОДЫ.md): для каждой сделки нового фьючерса — шорт 5 случайных ликвидных старых
монет (оборот ≥ 5 млн $ в сутки за 7 сут, фьючерс старше 60 сут) в тот же момент с тем же выходом 30/30/14; плюс ход индекса
альтов (s103/beta.index) за срок сделки. Запуск в папке периода после newlist3.py: MC_K=… MC_F=… python3 <repo>/research/s121/placebo3.py <метка>"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s103"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from beta import index  # noqa: E402
from newlist3 import SKIP  # noqa: E402


def main():
    lab = sys.argv[1]
    X = pd.read_pickle(f"s121_{lab}.pkl")
    tI, I, _, _ = index()
    rng = np.random.default_rng(5)
    syms = [s for s in K if s not in SKIP]
    pl, mk = [], []
    for s0, t0, net in zip(X.s, X.t, X["30/30/14"]):
        cand = []
        for s in syms:
            if s == s0:
                continue
            lo, hi = live(s)
            if lo > t0 - 60 * 86400 or hi < t0 + 15 * 86400:
                continue
            i = int(np.searchsorted(K[s]["t"] + 900, t0))
            if i >= len(K[s]["t"]) or K[s]["t"][i] + 900 != t0 or K[s]["qv"][max(0, i - 672):i + 1].sum() / 7 < 5e6:
                continue
            cand.append((s, i))
        ys = []
        for k in rng.permutation(len(cand))[:5]:
            s, i = cand[k]
            y = trade(s, i, tp=0.30, sl=0.30, hold_h=336, side=-1)
            if y:
                ys.append(y["net"])
        pl.append(np.mean(ys) if ys else np.nan)
        j0 = int(np.searchsorted(tI + 900, t0)); j1 = min(j0 + 336 * 4, len(I) - 1)
        mk.append(I[j1] / I[min(j0, len(I) - 1)] - 1)
    X["pl"] = pl; X["mkt"] = mk
    X.to_pickle(f"s121_{lab}.pkl")
    print(lab, "готово", len(X))


if __name__ == "__main__":
    main()
