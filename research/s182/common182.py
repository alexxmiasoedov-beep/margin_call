"""s182 — общие функции: периоды, t с кластерами по дню, разность средних «событие − контроль» (МНК с кластерами по дню),
объединение периодов, строка отчёта."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, OUT = 86400, "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"),
       "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-19", "2025-12-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def months(per):
    a, b, _ = PER[per]
    return (ts(b) - ts(a)) / (30.4 * DAY)


def ct(x, T):
    """Среднее и его t с кластерами по дням входа (как s43/oi_test.ct)."""
    y = np.asarray(x, float); g = (np.asarray(T, float) // DAY).astype(np.int64)
    m = ~np.isnan(y); y, g = y[m], g[m]
    if len(y) < 5:
        return np.nan, np.nan, len(y)
    u = pd.Series(y - y.mean()).groupby(g).sum().values
    G = len(u)
    se = np.sqrt((u ** 2).sum() * G / (G - 1)) / len(y) if G > 1 else np.nan
    return y.mean(), y.mean() / se if se and se > 0 else np.nan, len(y)


def diff(y, d, t):
    """Разность средних «d = 1 − d = 0» (МНК на признак) с ошибкой, кластеризованной по дню входа: (Δ, ошибка)."""
    y = np.asarray(y, float); d = np.asarray(d, float); t = np.asarray(t, float)
    m = ~np.isnan(y); y, d, t = y[m], d[m], t[m]
    if d.sum() < 5 or (1 - d).sum() < 5:
        return np.nan, np.nan
    Z = np.c_[np.ones(len(y)), d]; A = np.linalg.inv(Z.T @ Z); beta = A @ Z.T @ y; u = y - Z @ beta
    g = (t // DAY).astype(np.int64)
    S = pd.DataFrame(Z * u[:, None]).groupby(g).sum().to_numpy(); G = len(S)
    V = A @ (S.T @ S) @ A * G / (G - 1)
    return float(beta[1]), float(np.sqrt(V[1, 1]))


def combine(parts):
    """parts — [(Δ, ошибка, вес)]: среднее Δ с весами и его t (ошибки периодов независимы)."""
    p = [(d, s, w) for d, s, w in parts if np.isfinite(d) and np.isfinite(s) and w > 0]
    if not p:
        return np.nan, np.nan
    W = sum(w for _, _, w in p)
    m = sum(d * w for d, _, w in p) / W
    se = np.sqrt(sum((s * w) ** 2 for _, s, w in p)) / W
    return m, m / se


def line(x, per, col="net"):
    """Сделки части: число, в месяц, среднее (t), половины периода, с хеджем, сверх плацебо, стопов."""
    if len(x) < 5:
        return f"n={len(x)}"
    cut = ts(PER[per][2])
    m, t, n = ct(x[col], x.t)
    mh, th, _ = ct(x.hed, x.t) if "hed" in x else (np.nan, np.nan, 0)
    dp = x[col] - x.pl
    md, td, _ = ct(dp, x.t)
    st = (x.why == "стоп").mean() if "why" in x else np.nan
    return (f"n={n:4d} ({n / months(per):4.1f}/мес) {m:+.2%} (t {t:+.1f}) | половины {x[x.t < cut][col].mean():+.2%} / "
            f"{x[x.t >= cut][col].mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | сверх плацебо {md:+.2%} (t {td:+.1f}) | "
            f"стопов {st:.0%}")
