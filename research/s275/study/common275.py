"""s275 — общее для изучения связей между монетами (доходы сделок и правил не считаются).

Периоды (15-мин свечи, перпы USDT-M):
- «2020–2022»: s117/k_2020.pkl, окно 01.10.2020–01.10.2022;
- «2022–2024»: s117/k_oos.pkl, окно 01.10.2022–01.10.2024; **отрезок замысла 01.10.2022–01.10.2023** — только на нём
  считаются описательные статистики пар и остатков (корреляции, коинтеграция, полураспад, автокорреляции);
- «2024–2026»: s224/k_d.pkl (по 19.11.2026), окно 01.10.2024–19.10.2026 и свежий отрезок 19.10–20.11.2026.
Вселенная суток — 100 криптоперпов с наибольшим оборотом за прошлые 30 сут (`common271.liquid_rank`, возраст ≥ 30 сут).
Сектора — research/s275/sectors.csv (`sectors.py`).

Часовая цена — закрытие последней 15-мин свечи часа, только если в ней были сделки (иначе пропуск: устаревшая цена
неликвидной монеты даёт ложный «возврат», Lo–MacKinlay). Запуск скриптов — из /home/user/mc_data, python3 -I."""
import csv
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "s271", "study"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "s259", "study"))
from common259 import base, crypto_perps  # noqa: E402,F401
from common271 import cooldown, liquid_rank  # noqa: E402,F401

DAY, H, BAR = 86400, 3600, 900
MONTH = 30.44 * DAY
TMP = "/dev/shm/s275"
OUT = "/home/user/mc_data/s275"
os.makedirs(TMP, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


PER = {
    "2020–2022": dict(k="s117/k_2020.pkl", t0=ts("2020-10-01"), t1=ts("2022-10-01"), mid=ts("2021-10-01"), tb=None),
    "2022–2024": dict(k="s117/k_oos.pkl", t0=ts("2022-10-01"), t1=ts("2024-10-01"), mid=ts("2023-10-01"), tb=None),
    "2024–2026": dict(k="s224/k_d.pkl", t0=ts("2024-10-01"), t1=ts("2026-10-19"), mid=ts("2025-10-01"),
                      tb=ts("2026-11-20")),
}
DESIGN = (ts("2022-10-01"), ts("2023-10-01"))        # отрезок замысла
SKIP_EXTRA = {"BTCDOM", "DEFI", "ALL", "FOOTBALL", "BLUEBIRD"}   # индексные перпы


def load_k(per):
    return pickle.load(open(PER[per]["k"], "rb"))


def perps(K):
    return [p for p in crypto_perps(K) if base(p) not in SKIP_EXTRA]


def sectors():
    """перп → dict(sector, subsector, eco)."""
    f = os.path.join(HERE, "..", "sectors.csv")
    out = {}
    for r in csv.DictReader(open(f)):
        out[r["perp"]] = dict(sector=r["sector"], subsector=r["subsector"], eco=r["eco"], coin=r["coin"])
    return out


def universe(K, P, per, top=100):
    """Начало суток → множество top перпов (кэш в памяти /dev/shm)."""
    f = f"{TMP}/liq{top}_{per}.pkl"
    if os.path.exists(f):
        return pickle.load(open(f, "rb"))
    LR = liquid_rank(K, P, per, top=top, window=30)
    pickle.dump(LR, open(f, "wb"))
    return LR


def panel(K, P, t0, t1, step=H):
    """Матрицы (перп × шаг) на сетке [t0, t1): log-цена на конце шага (последняя 15-мин свеча шага со сделками)
    и оборот за шаг. step — H (час) или BAR (15 мин)."""
    n = int((t1 - t0) // step)
    LC = np.full((len(P), n), np.nan, np.float64)
    QV = np.zeros((len(P), n), np.float64)
    for k, p in enumerate(P):
        a = K[p]
        t = a["t"].astype(np.int64)
        m = (t >= t0) & (t < t1)
        if not m.any():
            continue
        tt = t[m]; c = a["c"][m].astype(np.float64); q = a["qv"][m].astype(np.float64)
        h = (tt - t0) // step
        np.add.at(QV[k], h, q)
        last = ((tt - t0) % step) == step - BAR
        ok = last & (q > 0) & (c > 0)
        LC[k, h[ok]] = np.log(c[ok])
    T = t0 + step * (np.arange(n) + 1)                    # конец шага
    return T, LC, QV


def in_universe(T, P, LR, lag=0):
    """Маска (перп × шаг): перп во вселенной суток, к которым относится начало шага."""
    days = ((T - 1) // DAY) * DAY
    M = np.zeros((len(P), len(T)), bool)
    pidx = {p: k for k, p in enumerate(P)}
    for d in np.unique(days):
        S = LR.get(int(d))
        if not S:
            continue
        cols = np.flatnonzero(days == d)
        rows = [pidx[p] for p in S if p in pidx]
        M[np.ix_(rows, cols)] = True
    return M


def ols_resid(y, X, ok):
    """МНК y на X (столбцы) по строкам ok; возвращает коэффициенты (или None)."""
    if ok.sum() < X.shape[1] * 20:
        return None
    b, *_ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
    return b


def adf_t(u, p=1):
    """t-статистика ADF для ряда u (с константой, p лагов разностей). Для остатков Энгла–Грейнджера с двумя рядами
    5%-й порог MacKinnon ≈ −3,34 (1% −3,90)."""
    u = np.asarray(u, float)
    u = u[np.isfinite(u)]
    if len(u) < 50:
        return np.nan
    du = np.diff(u)
    y = du[p:]
    cols = [np.ones(len(y)), u[p:-1]]
    for j in range(1, p + 1):
        cols.append(du[p - j:-j])
    X = np.column_stack(cols)
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    s2 = e @ e / (len(y) - X.shape[1])
    cov = s2 * np.linalg.inv(X.T @ X)
    return b[1] / np.sqrt(cov[1, 1])


def half_life(u):
    """Полураспад по AR(1): Δu = a + b·u(−1) → HL = −ln2 / ln(1 + b) (в шагах); nan, если b ≥ 0."""
    u = np.asarray(u, float)
    u = u[np.isfinite(u)]
    if len(u) < 50:
        return np.nan
    du = np.diff(u); x = u[:-1]
    X = np.column_stack([np.ones(len(x)), x])
    b, *_ = np.linalg.lstsq(X, du, rcond=None)
    if b[1] >= 0 or b[1] <= -1:
        return np.nan if b[1] >= 0 else 0.0
    return -np.log(2) / np.log(1 + b[1])


def rate(n, t0, t1):
    return n / ((t1 - t0) / MONTH)


def freq_line(T, per, cfg=None):
    cfg = cfg or PER[per]
    T = np.asarray(T, np.int64)
    t0, t1, mid, tb = cfg["t0"], cfg["t1"], cfg["mid"], cfg.get("tb")
    a = T[(T >= t0) & (T < t1)]
    out = dict(n=len(a), pm=rate(len(a), t0, t1), h1=rate(((a >= t0) & (a < mid)).sum(), t0, mid),
               h2=rate(((a >= mid) & (a < t1)).sum(), mid, t1))
    if tb:
        out["b"] = rate(((T >= t1) & (T < tb)).sum(), t1, tb)
    return out


def fmt(d):
    s = f"{d['pm']:7.1f} в мес. (n={d['n']}; половины {d['h1']:.1f} / {d['h2']:.1f}"
    if "b" in d:
        s += f"; свежий отрезок {d['b']:.1f}"
    return s + ")"
