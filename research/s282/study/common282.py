"""s282 — общее для подсчёта частот «прострелов» (изучение; доходы сделок и всё, что было после касания, не считаются).

Периоды (свечи 15 мин, dict «перп → dict массивов t, o, h, l, c, qv, tb, n», t — открытие свечи, с):
- 2020–2022: s117/k_2020.pkl (163 перпа), окно 01.10.2020–01.10.2022, половины по 01.10.2021;
- 2022–2024: s117/k_oos.pkl (327 перпов), окно 01.10.2022–01.10.2024, половины по 01.10.2023;
- 2024–2026: s2/k2y.pkl (869 перпов), окно 01.10.2024–19.10.2026, половины по 01.10.2025; у неторгующихся перпов
  свечи-заглушки без оборота — берутся только свечи с qv > 0.
Вселенная — криптоперпы USDT-M (`s259/study/common259.crypto_perps`: без TradFi, индексов, стейблкоинов и металлов).
Запуск скриптов — из /home/user/mc_data: python3 -I <repo>/research/s282/study/<скрипт>.py
Крупные промежуточные таблицы — /dev/shm/s282 (диск почти полон), итоговые небольшие — /home/user/mc_data/s282."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "s259", "study"))
from common259 import base, crypto_perps  # noqa: E402,F401

DAY, H, BAR = 86400, 3600, 900
MONTH = 30.44 * DAY
TMP = "/dev/shm/s282"
OUT = "/home/user/mc_data/s282"
os.makedirs(TMP, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

X_LEVELS = (0.03, 0.05, 0.08, 0.10, 0.15)          # уход минимума (максимума) от закрытия прошлой свечи
K_LEVELS = (4, 6, 8, 10, 15)                       # то же в долях медианного размаха 15-мин свечи монеты за 7 сут
TURN_BINS = (0, 1e6, 5e6, 20e6, 100e6, np.inf)     # оборот перпа за прошлые 24 ч, $
TURN_LAB = ("< 1 млн $", "1–5 млн $", "5–20 млн $", "20–100 млн $", "≥ 100 млн $")


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


PER = {
    "2020–2022": dict(k="s117/k_2020.pkl", t0=ts("2020-10-01"), t1=ts("2022-10-01"), mid=ts("2021-10-01")),
    "2022–2024": dict(k="s117/k_oos.pkl", t0=ts("2022-10-01"), t1=ts("2024-10-01"), mid=ts("2023-10-01")),
    "2024–2026": dict(k="s2/k2y.pkl", t0=ts("2024-10-01"), t1=ts("2026-10-19"), mid=ts("2025-10-01")),
}


def months(t0, t1):
    return (t1 - t0) / MONTH


def cooldown_mask(coin, t, gap):
    """Маска «первое событие монеты за gap секунд» (отсчёт от последнего взятого); вход отсортирован по (coin, t)."""
    keep = np.zeros(len(t), bool)
    last_c, last_t = None, -10 ** 18
    for k in range(len(t)):
        if coin[k] != last_c:
            last_c, last_t = coin[k], -10 ** 18
        if t[k] - last_t >= gap:
            keep[k] = True
            last_t = t[k]
    return keep
