"""s103 — слабеют ли механизмы журналов со временем: доход по кварталам (как есть и с хеджем индексом альтов, beta.py)
и наклон по времени (регрессия дохода сделки на время входа в годах, t с кластерами по дням). Запуск из папки с данными
после beta.py: python3 <repo>/research/s103/decay.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import DAY  # noqa: E402


def slope(y, t):
    """Наклон дохода по времени (в долях за год) и его t с кластерами по дням."""
    x = (t - t.mean()) / (365 * DAY)
    X = np.c_[np.ones(len(x)), x]
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    g = (t // DAY).astype(np.int64)
    S = pd.DataFrame(X * e[:, None]).groupby(g).sum().values
    V = np.linalg.inv(X.T @ X) @ (S.T @ S) @ np.linalg.inv(X.T @ X)
    return b[1], b[1] / np.sqrt(V[1, 1])


X = pd.read_pickle("s103/beta_trades.pkl")
X["q"] = pd.to_datetime(X.t, unit="s").dt.to_period("Q").astype(str)
qs = sorted(X.q.unique())
print("Доход на сделку по кварталам, с хеджем индексом альтов (в скобках — сделок):")
print(f"{'':5s} " + " ".join(f"{q[2:]:>11s}" for q in qs) + "   наклон за год")
for j, x in sorted(X.groupby("j"), key=lambda z: -len(z[1])):
    if len(x) < 100:
        continue
    g = x.groupby("q").h.agg(["mean", "size"])
    cells = [f"{g.at[q, 'mean']:+6.2%}({g.at[q, 'size']:3d})" if q in g.index else " " * 11 for q in qs]
    b, tb = slope(x.h.values, x.t.values.astype(float))
    br, tr = slope(x.r.values, x.t.values.astype(float))
    print(f"{j:5s} " + " ".join(cells) + f"   {b:+6.2%} (t {tb:+4.1f}); как есть {br:+6.2%} (t {tr:+4.1f})")
