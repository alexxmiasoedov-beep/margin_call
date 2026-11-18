"""s167 — разрезы Р1 (ход за 24 ч до входа −5…+5%) и Р2 (≥ 1% против 0,5–1%) на сделках s167 на Binance (запись — ВЫВОДЫ.md,
до расчёта). Ход — по 15-мин свечам периода. Запуск в папке периода с MC_K/MC_F/MC_CUT: python3 <repo>/research/s167/slices.py
<период>; сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY = "/home/user/mc_data", 86400


def run(per):
    from common import K  # noqa: E402
    X = pd.read_pickle(f"{OUT}/s167_{per}.pkl"); X = X[X.exch == "Binance"].copy()
    r24 = []
    for r in X.itertuples():
        t, c = K[r.s]["t"].astype(np.int64) + 900, K[r.s]["c"].astype(float)
        i = int(np.searchsorted(t, r.t, "right")) - 1; j = int(np.searchsorted(t, r.t - DAY, "right")) - 1
        r24.append(c[i] / c[j] - 1 if i >= 0 and j >= 0 and t[i] == r.t and t[j] == r.t - DAY else np.nan)
    X["r24"] = r24
    X.to_pickle(f"{OUT}/s167s_{per}.pkl")
    print(per, len(X), "с ходом", int(X.r24.notna().sum()), flush=True)


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per in ("2020–2022", "2022–2024"):
        X = pd.read_pickle(f"{OUT}/s167s_{per}.pkl"); X["per"] = per; A.append(X)
        c = X[(X.r24 >= -0.05) & (X.r24 <= 0.05)]
        m, t, n = ct(c.net, c.t)
        big, small = X[X.frac >= 0.01], X[X.frac < 0.01]
        print(f"{per}: Р1 спокойный рынок n={n} {m:+.2%} (t {t:+.1f}) | прочие {X[~X.index.isin(c.index)].net.mean():+.2%} "
              f"({len(X) - len(c)}) | Р2 ≥ 1% {big.net.mean():+.2%} ({len(big)}) против 0,5–1% {small.net.mean():+.2%} ({len(small)})")
    A = pd.concat(A, ignore_index=True)
    c = A[(A.r24 >= -0.05) & (A.r24 <= 0.05)]
    m, t, n = ct(c.net, c.t); mh, th, _ = ct(c.hed.dropna(), c.t[c.hed.notna()])
    print(f"вместе: Р1 n={n} {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f}) | Р2 ≥ 1% {A[A.frac >= 0.01].net.mean():+.2%} "
          f"против 0,5–1% {A[A.frac < 0.01].net.mean():+.2%}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
