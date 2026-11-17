"""s108 — карта лонга, исправленная (только первая половина: вход и выход до 01.12.2025):
1) какие монеты лучше других в тот же день — доход лонга за 7 сут минус среднее всех монет этого дня, децили признака
   внутри дня (календарные волны рынка не мешают);
2) когда растёт весь рынок — среднее дня против рыночных признаков (средний фандинг, ход индекса альтов и BTC).
Возраст — только у монет, чей фьючерс запущен после начала архива (иначе «старая»). Панель — s108/panel.pkl (long_map.py).
Запуск из папки с данными: python3 <repo>/research/s108/long_map2.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

X = pd.read_pickle("s108/panel.pkl")
t0 = float(K["BTC"]["t"][0])
first = {s: live(s)[0] for s in X.s.unique()}
X["new"] = X.s.map(lambda s: first[s] > t0 + 3 * DAY)
X["age"] = np.where(X.new, X.age, np.nan)
F = X[X.t + 7 * DAY < CUT].copy()
F["x7"] = F.L7 - F.groupby("t").L7.transform("mean")
F["x1"] = F.L1 - F.groupby("t").L1.transform("mean")
print(f"первая половина: {len(F)} строк, дней {F.t.nunique()}; новых монет (листинг внутри архива): {F[F.new].s.nunique()}")
print("\n1) Монета против рынка того же дня: доход лонга за 7 сут сверх среднего дня, децили признака внутри дня")
for col in ("r1", "r7", "r30", "hi30", "vol7", "fund3", "lv", "krs", "sps", "age"):
    x = F[F[col].notna()].copy()
    x["q"] = x.groupby("t")[col].rank(pct=True, method="first")
    x["q"] = np.minimum((x.q * 10).astype(int), 9)
    cells = []
    for k in range(10):
        y = x[x.q == k]
        m, tt, _ = ct(y.x7, y.t) if len(y) > 30 else (np.nan, np.nan, 0)
        cells.append(f"{m:+5.1%}({tt:+.1f})")
    print(f"  {col:6s} " + " ".join(cells))
print("\n2) Весь рынок: средний лонг дня на 7 сут по рыночным признакам (терцили)")
D = F.groupby("t").agg(L7=("L7", "mean"), L1=("L1", "mean"), fund=("fund3", "mean"), idx7=("idx7", "first"),
                       btc7=("btc7", "first"), up=("idx_up", "first"), r7m=("r7", "median")).reset_index()
for col in ("fund", "idx7", "btc7", "r7m"):
    q = pd.qcut(D[col], 3, labels=["низ", "середина", "верх"])
    cells = []
    for k in ["низ", "середина", "верх"]:
        y = D[q == k]
        cells.append(f"{k}: {y.L7.mean():+.2%} (дней {len(y)})")
    print(f"  {col:5s} " + " | ".join(cells))
print("  индекс выше 20-дн. средней: " + " | ".join(f"{u}: {D[D.up == u].L7.mean():+.2%} (дней {(D.up == u).sum()})" for u in (True, False)))
F.to_pickle("s108/panel_first.pkl")
