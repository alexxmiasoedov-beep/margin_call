"""s271 Г7 — частота запусков новых криптоперпов USDT-M (и снятий — для справки). Доходы не считаются.

Новый перп — первая 15-мин свеча с оборотом внутри окна периода, не раньше чем через 2 сут после начала архива; для
сделки Г7 нужно ≥ 8 ч живых свечей после первой. Группы: спот Binance уже был или открылся не позже чем через 1 ч после
первой свечи перпа (2024–2026 гг.: `spot_start`), иначе «без спота». Снятие — последняя свеча с оборотом раньше конца
архива на ≥ 2 сут. Запуск из /home/user/mc_data: python3 -I <repo>/research/s271/study/freq_listing.py"""
import collections
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common271 import BAR, DAY, PER, crypto_perps, fmt, freq_line, live_idx, load_k, spot_start  # noqa: E402


def run(per):
    cfg = PER[per]
    K = load_k(per)
    P = crypto_perps(K)
    ss = spot_start(P) if per == "2024–2026" else {}
    t_arch0 = min(int(K[p]["t"][0]) for p in P)
    t_arch1 = max(int(K[p]["t"][-1]) for p in P)
    new, new_spot, new_nospot, gone, hours = [], [], [], [], collections.Counter()
    for p in P:
        a = K[p]
        i0, i1 = live_idx(a)
        if i0 is None:
            continue
        t = a["t"].astype(np.int64)
        tf, tl = int(t[i0]), int(t[i1])
        if tf >= t_arch0 + 2 * DAY and i1 - i0 >= 32:
            new.append(tf)
            hours[(tf % DAY) // 3600] += 1
            if per == "2024–2026":
                s0 = ss.get(p)
                (new_spot if (s0 is not None and s0 <= tf + 3600) else new_nospot).append(tf)
        if tl + BAR <= t_arch1 - 2 * DAY:
            gone.append(tl)
    print(f"\n== {per}: криптоперпов в архиве {len(P)}")
    print("Г7 новые перпы (≥ 8 ч свечей):", fmt(freq_line(new, cfg["t0"], cfg["t1"], cfg["mid"], cfg["tb"])))
    if per == "2024–2026":
        print("   со спотом Binance к запуску:", fmt(freq_line(new_spot, cfg["t0"], cfg["t1"], cfg["mid"], cfg["tb"])))
        print("   без спота Binance:          ", fmt(freq_line(new_nospot, cfg["t0"], cfg["t1"], cfg["mid"], cfg["tb"])))
    print("Снятия перпов:", fmt(freq_line(gone, cfg["t0"], cfg["t1"], cfg["mid"], cfg["tb"])))
    s = pd.Series(1, index=pd.to_datetime(np.array(new), unit="s", utc=True)).resample("QS").sum()
    print("Новые по кварталам:", " ".join(f"{d:%Y-%m}:{v}" for d, v in s.items()))
    tot = sum(hours.values())
    print("Час запуска UTC (доля, %):", " ".join(f"{h:02d}:{100 * hours[h] / tot:.0f}" for h in range(24) if hours[h]))


if __name__ == "__main__":
    for per in PER:
        run(per)
