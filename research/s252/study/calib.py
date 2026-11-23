"""s252 — калибровка пересчёта окон на месяц на полном сборе Ethereum: события (а)/(б) ≥ 0,5% у перпов без спота
(s252/eth_nospot.pkl, без перекладки) считаются двумя способами за 01–11.2026 — (1) настоящие «первые у монеты за 48 ч» в месяц,
(2) как в пилоте BNB Chain: «монето-окна» с событием в тех же 12-часовых окнах (s252/windows.json) × 730,5 / часы окон.
Отношение (1)/(2) показывает, насколько пилот завышает «первые за 48 ч» из-за пачек; устойчивая оценка — по 2000
случайным окнам. Только частоты.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/calib.py"""
import json
import os
import random

import pandas as pd


def main():
    X = pd.read_pickle("s252/eth_nospot.pkl")
    W = json.load(open("s252/windows.json"))
    done = [w for w in W if os.path.exists(f"s252/rawwin/done_{w['id']}") and w["t0"] >= 1767225600]   # окна 2026 г.
    if not done:
        print("нет собранных окон 2026 г.")
        return
    hrs = sum((w["t1"] - w["t0"]) / 3600 for w in done)
    for cls in ("а", "б"):
        Y = X[X.cls == cls]
        real = Y[Y.f48c & (Y.t >= 1767225600) & (Y.t < 1794700800)]
        months = (1794700800 - 1767225600) / 86400 / 30.44
        cw = 0
        for w in done:
            Z = Y[(Y.t >= w["t0"]) & (Y.t < w["t1"])]
            cw += Z.perp.nunique()
        est = cw * 730.5 / hrs
        print(f"класс ({cls}): настоящих «первых за 48 ч» {len(real) / months:.1f} в месяц; оценка по {len(done)} окнам "
              f"({hrs:.0f} ч): {est:.1f} в месяц (монето-окон {cw}); отношение {len(real) / months / est:.2f}" if est else
              f"класс ({cls}): настоящих {len(real) / months:.1f} в месяц; в окнах событий нет")
        rng, N, tot = random.Random(1), 2000, 0              # то же по 2000 случайным окнам 12 ч 2026 г. — устойчивая оценка
        for _ in range(N):
            t0 = rng.randrange(1767225600, 1794700800 - 43200)
            tot += Y[(Y.t >= t0) & (Y.t < t0 + 43200)].perp.nunique()
        est2 = tot * 730.5 / (N * 12)
        print(f"   по {N} случайным окнам: оценка {est2:.1f} в месяц, отношение {len(real) / months / est2:.2f}")


if __name__ == "__main__":
    main()
