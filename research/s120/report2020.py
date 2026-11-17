"""s120 — шорт пампов после роста рынка альтов на третьем периоде 10.2020–09.2022 (правило — ВЫВОДЫ.md, записано до сборки
данных). Вход — ~/mc_2020/s119_y2020.pkl (regime.py y2020 после s118/spot_oos.py с MC_Y0=2020) и для шести лет — сделки
двух других периодов (s119_old.pkl, s119_new.pkl). Запуск: python3 <repo>/research/s120/report2020.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import DAY, ct  # noqa: E402

P = {"2020–2022": pd.read_pickle("/home/user/mc_2020/s119_y2020.pkl"), "2022–2024": pd.read_pickle("/home/user/mc_oos/s119_old.pkl"),
     "2024–2026": pd.read_pickle("/home/user/mc_data/s119_new.pkl")}
mid = pd.Timestamp("2021-10-01", tz="UTC").timestamp()
for tl, tf in (("🛒-тип (спот ≥ 25,9%)", lambda x: x.share >= 0.259), ("все пампы", lambda x: x.net.notna())):
    print(f"\n=== {tl} ===")
    for fl, ff in (("без фильтра", lambda x: x.net.notna()), ("альты за 30 сут выросли (правило)", lambda x: x.idx30 >= 0),
                   ("альты за 30 сут упали", lambda x: x.idx30 < 0)):
        cells, allx = [], []
        for pl, X in P.items():
            x = X[tf(X) & ff(X) & X.net.notna()]
            months = (X.t.max() - X.t.min()) / (30.4 * DAY)
            m, t, n = ct(x.net, x.t) if len(x) >= 5 else (np.nan, np.nan, len(x))
            extra = ""
            if pl == "2020–2022" and len(x) >= 5:
                h1, h2 = x[x.t < mid], x[x.t >= mid]
                extra = f" [половины {h1.net.mean():+.2%} ({len(h1)}) / {h2.net.mean():+.2%} ({len(h2)})]"
            cells.append(f"{pl}: n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}){extra}")
            allx.append(x)
        a = pd.concat(allx); m, t, n = ct(a.net, a.t)
        print(f"  {fl:34s} | " + " | ".join(cells) + f" | 6 лет: n={n} {m:+6.2%} (t {t:+4.1f})")
