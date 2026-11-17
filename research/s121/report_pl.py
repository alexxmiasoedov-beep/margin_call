"""s121 — сводка плацебо и хеджа по трём периодам (после placebo3.py). Запуск из любой папки."""
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import ct  # noqa: E402

P = {"2020–2022": "/home/user/mc_2020/s121_2020.pkl", "2022–2024": "/home/user/mc_oos/s121_2022.pkl", "2024–2026": "/home/user/mc_data/s121_2024.pkl"}
P = {k: pd.read_pickle(v) for k, v in P.items()}
rows = []
for k, X in P.items():
    x = X[X["30/30/14"].notna()].copy()
    x["d"] = x["30/30/14"] - x.pl; x["h"] = x["30/30/14"] + x.mkt
    m, t, n = ct(x["30/30/14"], x.t); dp, tp, _ = ct(x.d, x.t); hm, th, _ = ct(x.h, x.t)
    print(f"{k}: n={n} сделка {m:+.2%} (t {t:+.1f}) | плацебо {x.pl.mean():+.2%} | разница {dp:+.2%} (t {tp:+.1f}) | с хеджем индексом {hm:+.2%} (t {th:+.1f})")
    rows.append(x)
a = pd.concat(rows)
m, t, n = ct(a["30/30/14"], a.t); dp, tp, _ = ct(a.d, a.t); hm, th, _ = ct(a.h, a.t)
print(f"6 лет: n={n} сделка {m:+.2%} (t {t:+.1f}) | плацебо {a.pl.mean():+.2%} | разница {dp:+.2%} (t {tp:+.1f}) | с хеджем {hm:+.2%} (t {th:+.1f})")
q = pd.to_datetime(a.t, unit="s").dt.to_period("Q")
print("по кварталам:", " ".join(f"{k}:{g['30/30/14'].mean():+.1%}({len(g)})" for k, g in a.groupby(q)))
by = a.groupby("s")["30/30/14"].sum().sort_values(ascending=False)
print(f"без 10 лучших монет: {a[~a.s.isin(by.head(10).index)]['30/30/14'].mean():+.2%}; стопов {(a.why == 'стоп').mean():.0%}, тейков {(a.why == 'тейк').mean():.0%}")
