"""s119 — сводка режимных фильтров по двум периодам (после regime.py new и old). Запуск из любой папки:
python3 <repo>/research/s119/report.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s43"))
from oi_test import DAY, ct  # noqa: E402

P = {"2022–2024": pd.read_pickle("/home/user/mc_oos/s119_old.pkl"), "2024–2026": pd.read_pickle("/home/user/mc_data/s119_new.pkl")}
TYPES = {"🇰🇷-тип (Корея ≥ 20%)": lambda x: x.kr >= 0.2, "🛒-тип (спот ≥ 25,9%)": lambda x: x.share >= 0.259,
         "все пампы": lambda x: x.net.notna()}
FILT = {"без фильтра": lambda x: x.net.notna(), "Ф1: альты за 30 сут упали": lambda x: x.idx30 < 0,
        "  обратное: альты за 30 сут выросли": lambda x: x.idx30 >= 0, "Ф2: недавние шорты в плюсе": lambda x: x.recent > 0,
        "Ф1 и Ф2": lambda x: (x.idx30 < 0) & (x.recent > 0)}
for tl, tf in TYPES.items():
    print(f"\n=== {tl} ===")
    for fl, ff in FILT.items():
        cells, allx = [], []
        for pl, X in P.items():
            x = X[tf(X) & ff(X) & X.net.notna()]
            months = (X.t.max() - X.t.min()) / (30.4 * DAY)
            m, t, n = ct(x.net, x.t) if len(x) >= 5 else (np.nan, np.nan, len(x))
            cells.append(f"{pl}: n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f})")
            allx.append(x)
        a = pd.concat(allx)
        m, t, n = ct(a.net, a.t) if len(a) >= 5 else (np.nan, np.nan, len(a))
        print(f"  {fl:36s} | " + " | ".join(cells) + f" | 4 года: {m:+6.2%} (t {t:+4.1f})")
