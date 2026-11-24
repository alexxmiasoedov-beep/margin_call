"""s271 — общее для подсчёта частот событий (изучение; доходы сделок и правил не считаются).

Периоды (свечи 15 мин, фандинг, часовые метрики OI):
- «2022–2024»: s117/k_oos.pkl (327 перпов выборки s117), s230/metrics — окно 01.10.2022–01.10.2024, половины по 01.10.2023;
- «2024–2026»: s224/k_d.pkl (по 19.11.2026), s228/met — основное окно А 01.10.2024–19.10.2026 (как s259/s260),
  половины по 01.10.2025; свежий отрезок Б 19.10–20.11.2026 (премия s12 и спот s23 есть только по 18.10.2026).
Вселенная — криптоперпы USDT-M (`s259/study/common259.crypto_perps`: без TradFi, индексов, стейблкоинов и металлов).
Запуск скриптов — из /home/user/mc_data: python3 -I <repo>/research/s271/study/<скрипт>.py
Крупные промежуточные таблицы — в памяти, /dev/shm/s271 (диск почти полон)."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "s259", "study"))
from common259 import base, crypto_perps, spot_start  # noqa: E402,F401

DAY, H, BAR = 86400, 3600, 900
MONTH = 30.44 * DAY
TMP = "/dev/shm/s271"
os.makedirs(TMP, exist_ok=True)


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


PER = {
    "2022–2024": dict(k="s117/k_oos.pkl", met="s230/metrics", t0=ts("2022-10-01"), t1=ts("2024-10-01"),
                      mid=ts("2023-10-01"), tb=None),
    "2024–2026": dict(k="s224/k_d.pkl", met="s228/met", t0=ts("2024-10-01"), t1=ts("2026-10-19"),
                      mid=ts("2025-10-01"), tb=ts("2026-11-20")),
}


# третий период — только для правил уровней и баз (freq_levels.py); метрик OI за 2020–2022 гг. у нас нет
PER_ALL = {"2020–2022": dict(k="s117/k_2020.pkl", met=None, t0=ts("2020-10-01"), t1=ts("2022-10-01"),
                             mid=ts("2021-10-01"), tb=None), **PER}


def load_k(per):
    return pickle.load(open(PER_ALL[per]["k"], "rb"))


def live_idx(a):
    nz = np.flatnonzero(a["qv"] > 0)
    return (int(nz[0]), int(nz[-1])) if len(nz) else (None, None)


def met(per, p):
    """Часовые метрики: t (с, отметка HH:00), oi (монет), oi_usd. None — файла нет."""
    d = PER[per]["met"]
    if d.endswith("/met"):
        f = f"{d}/{p}.npz"
        if not os.path.exists(f):
            return None
        z = np.load(f)
        return z["t"].astype(np.int64), z["v"][:, 0].astype(float), z["v"][:, 1].astype(float)
    f = f"{d}/{p}.npy"
    if not os.path.exists(f):
        return None
    a = np.load(f, allow_pickle=True)
    if a.ndim != 2 or not len(a):
        return None
    return a[:, 0].astype(np.int64), a[:, 1].astype(float), a[:, 2].astype(float)


def hourly_close(a):
    """Цена на отметке часа T = закрытие 15-мин свечи, открытой в T − 15 мин. Возвращает (T, цена, оборот часа до T)."""
    t = a["t"].astype(np.int64)
    j = np.flatnonzero((t + BAR) % H == 0)
    j = j[j >= 3]
    j = j[t[j - 3] == t[j] - 3 * BAR]
    cs = np.r_[0.0, np.cumsum(a["qv"].astype(float))]
    return t[j] + BAR, a["c"][j].astype(float), cs[j + 1] - cs[j - 3]


def rate(n_events, t0, t1):
    return n_events / ((t1 - t0) / MONTH)


def freq_line(T, t0, t1, mid, tb=None, t_end=None):
    """Строка частот: в месяц за окно [t0, t1), по половинам и на свежем отрезке [t1, tb)."""
    T = np.asarray(T, np.int64)
    a = T[(T >= t0) & (T < t1)]
    out = dict(n=len(a), pm=rate(len(a), t0, t1),
               h1=rate(((a >= t0) & (a < mid)).sum(), t0, mid), h2=rate(((a >= mid) & (a < t1)).sum(), mid, t1))
    if tb:
        b = T[(T >= t1) & (T < tb)]
        out["b"] = rate(len(b), t1, tb)
    return out


def fmt(d):
    s = f"{d['pm']:7.1f} в мес. (n={d['n']}; половины {d['h1']:.1f} / {d['h2']:.1f}"
    if "b" in d:
        s += f"; свежий отрезок {d['b']:.1f}"
    return s + ")"


def cooldown(T, gap):
    """Индексы событий не чаще одного на gap секунд (отсчёт от последнего взятого)."""
    keep, last = [], -10 ** 18
    for k, x in enumerate(T):
        if x - last >= gap:
            keep.append(k); last = x
    return np.array(keep, dtype=np.int64)


def liquid_rank(K, P, per, top=100, window=30):
    """Для каждой суток UTC — множество top перпов по суммарному обороту за прошлые window сут (возраст ≥ window сут).
    Возвращает dict: начало суток → set(перп)."""
    days = {}
    for p in P:
        a = K[p]
        t = a["t"].astype(np.int64)
        d = (t // DAY) * DAY
        q = pd.Series(a["qv"].astype(float)).groupby(d).sum()
        roll = q.rolling(window, min_periods=window).sum().shift(1)
        nz = np.flatnonzero(a["qv"] > 0)
        if not len(nz):
            continue
        first = (int(t[nz[0]]) // DAY) * DAY
        for day, v in roll.dropna().items():
            if day - first >= window * DAY and v > 0:
                days.setdefault(int(day), []).append((v, p))
    return {d: {p for _, p in sorted(v, reverse=True)[:top]} for d, v in days.items()}
