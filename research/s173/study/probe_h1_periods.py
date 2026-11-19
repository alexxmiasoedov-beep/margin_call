"""s173 — частота H1 («возврат в зону застрявших покупателей») на трёх периодах, без доходов.
Запуск: python3 -I probe_h1_periods.py <папка данных>"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from probe_freq import NONCRYPTO, h1_events, hourly, month, roll_sum  # noqa: E402

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
kind = pd.read_pickle(os.path.join(D, "s12/perp_kind.pkl"))
BAD = set(kind.get("tradfi", set())) | NONCRYPTO

for name, path in (("2020–2022", "s117/k_2020.pkl"), ("2022–2024", "s117/k_oos.pkl")):
    with open(os.path.join(D, path), "rb") as f:
        K = pickle.load(f)
    rows, univ = [], []
    for s in K:
        if s in BAD or s.endswith("USDC") or "tb" not in K[s]:
            continue
        T, x = hourly(K[s])
        if len(T) < 24 * 40:
            continue
        v24 = roll_sum(x["qv"], 24)
        univ.append(((T % 24 == 0) & (v24 >= 5e6)).sum())
        for t, dz, pmp in h1_events(T, x, dens_min=0.15):
            rows.append((s, t, dz, pmp))
    m = pd.Series([month(np.int64(r[1])) for r in rows]).value_counts().sort_index()
    full = m.iloc[1:-1]
    ndays = len(set(int(r[1]) // 24 for r in rows))
    print(f"{name}: монет {len(K)}, H1 (плотность ≥ 15%) событий {len(rows)}, в месяц медиана {full.median():.0f}, "
          f"среднее {full.mean():.0f}, мин {full.min()}, макс {full.max()}; пампов {sum(r[3] for r in rows)}; "
          f"монето-дней вселенной {sum(univ)}")
    del K
