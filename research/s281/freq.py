"""s281 — частота сигналов «расписание монеты» (без доходов): |t| ≥ 3 и |m| ≥ 0,2% по остаткам того же часа прошлых 20 суток,
перп ≥ 30 сут, оборот за 24 ч ≥ 5 млн $. Запуск: python3 -I freq.py"""
import os
import sys
import warnings

import numpy as np

warnings.simplefilter("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common281 import DAY, MMIN, NMIN, TMIN, PER, grid, signal  # noqa: E402

for per in PER:
    P, T, R, E, v24, age, alt = grid(per)
    m, t, n = signal(E)
    ok = (n >= NMIN) & (age >= 30 * DAY) & (v24 >= 5e6) & np.isfinite(R)
    lo = ok & (t >= TMIN) & (m >= MMIN)
    sh = ok & (t <= -TMIN) & (m <= -MMIN)
    mo = (T[-1] - T[0]) / (30.44 * DAY)
    hod = (T // 3600) % 24
    fh = np.isin(hod, (0, 8, 16))
    print(f"{per}: перпов {len(P)}; сигналов лонг {lo.sum() / mo:.0f} в мес., шорт {sh.sum() / mo:.0f} в мес.; "
          f"в часы начисления 0/8/16 — {((lo | sh) & fh[None, :]).sum() / max((lo | sh).sum(), 1):.0%}; "
          f"монет с сигналом {np.flatnonzero((lo | sh).any(axis=1)).size}; монето-часов в выборке {ok.sum() / mo:.0f} в мес.; "
          f"доля сигналов {(lo | sh).sum() / ok.sum():.2%} (случай при |t| ≥ 3 и n=20 — около 0,8%)")
