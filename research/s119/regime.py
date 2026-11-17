"""s119 — режимные признаки для шортов пампов одного периода (гипотеза — ВЫВОДЫ.md). Период задаётся архивом (MC_K, MC_F)
и файлами сделок: 2024–2026 — s49/trades.pkl (kr, share, net); 2022–2024 — s118_kr.pkl и s118_spot.pkl в ~/mc_oos.
Ф1 — ход индекса альтов (s103/beta.index) за 30 сут до пампа; Ф2 — средний доход шортов всех пампов, открытых 32–2 сут назад.
Итог — s119_<период>.pkl в рабочей папке. Запуск: python3 <repo>/research/s119/regime.py new|old"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s103"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from oi_test import DAY  # noqa: E402
from beta import index  # noqa: E402


def load(period):
    if period == "new":
        X = pd.read_pickle("s49/trades.pkl")[["s", "t", "kr", "share", "net"]].copy()
        X["t"] = X.t.astype(float)
        return X
    A = pd.read_pickle("s118_kr.pkl")[["s", "t", "kr", "net"]]
    B = pd.read_pickle("s118_spot.pkl")[["s", "t", "share", "net"]]
    X = pd.merge(B, A[["s", "t", "kr"]], on=["s", "t"], how="left")             # все пампы — по spot_oos (одна на 48 ч)
    extra = A[~A.set_index(["s", "t"]).index.isin(X.set_index(["s", "t"]).index)].assign(share=np.nan)
    X = pd.concat([X, extra[["s", "t", "share", "net", "kr"]]], ignore_index=True)
    X["t"] = X.t.astype(float)
    return X


def main():
    period = sys.argv[1]
    tI, I, _, _ = index()
    X = load(period).sort_values("t").reset_index(drop=True)
    cl = tI + 900
    i = np.searchsorted(cl, X.t.values); i = np.clip(i, 30 * 96, len(I) - 1)
    X["idx30"] = I[i] / I[i - 30 * 96] - 1
    tt = X.t.values; nn = X.net.values
    X["recent"] = [np.nanmean(nn[(tt >= T - 32 * DAY) & (tt <= T - 2 * DAY)]) if ((tt >= T - 32 * DAY) & (tt <= T - 2 * DAY)).any()
                   else np.nan for T in tt]
    X.to_pickle(f"s119_{period}.pkl")
    print(period, len(X), "пампов; Ф1 (рынок альтов за 30 сут упал):", f"{(X.idx30 < 0).mean():.0%}",
          "| Ф2 (недавние шорты в плюсе):", f"{(X.recent > 0).mean():.0%}")


if __name__ == "__main__":
    main()
