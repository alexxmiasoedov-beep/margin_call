"""s173 — частота Г7 «ширина заводов»: число разных небиржевых отправителей с заводами ≥ 0,5% обращения на биржи
за 72 ч (события s160, только время и адреса — доходы не читаются). Запуск: python3 -I probe_breadth.py <папка данных>"""
import os
import sys

import numpy as np
import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
x = pd.read_pickle(os.path.join(D, "s160_events.pkl"))
x = x[(x.from_exch == False) & (x.perp.notna())].copy()  # noqa: E712
x["day"] = (x.t // 86400).astype(int)
ev = []
for tok, g in x.groupby("tok"):
    for d in np.sort(g.day.unique()):
        w = g[(g.day > d - 3) & (g.day <= d)]
        ev.append((tok, d, w.frm.nunique()))
E = pd.DataFrame(ev, columns=["tok", "day", "nsend"])
E["m"] = pd.to_datetime(E.day * 86400, unit="s").dt.to_period("M")
for k in (2, 3, 5):
    keep, last = [], {}
    for r in E[E.nsend >= k].sort_values("day").itertuples():
        if r.day - last.get(r.tok, -99) >= 7:
            keep.append(r); last[r.tok] = r.day
    pm = pd.DataFrame(keep).groupby("m").size()
    sub = pm[(pm.index >= "2024-10") & (pm.index < "2026-10")]
    print(f"отправителей ≥ {k} за 72 ч: событий {len(keep)}, в месяц 10.2024–09.2026 медиана {sub.median():.0f}, "
          f"за 2020–2026 в среднем {pm.mean():.1f}")
