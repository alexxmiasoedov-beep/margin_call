"""s254 — ⏰ в дни, когда закрыта биржа акций KRX (выходные, праздники Кореи, закрытия KRX), против рабочих дней KRX
(пробел C1 мета-анализа s212). Правило проверки — ВЫВОДЫ.md, записано до расчёта.

Сделки ⏰ — таблицы s88 (событие — час 00–01 UTC, рост перпа ≥ 5%, доля Кореи ≥ 20%; выход S_10_25 — тейк 10 / стоп 25 /
48 ч, комиссия и фандинг; плацебо — та же монета за 45/90/135 сут):
  10.2020–09.2022 — s88/oos2020_trades.pkl (s130), 10.2022–09.2024 — s88/oos_trades.pkl, 10.2024–10.2026 — s88/trades.pkl.
Календарь — пакет holidays (KR) и закрытия KRX сверх праздников (выборы, 1 мая, последний рабочий день года, временные
выходные). Запуск из /home/user/mc_data: python3 <repo>/research/s254/run.py [count|main]"""
import datetime as dt
import sys

import holidays
import numpy as np
import pandas as pd

DAY, WEEK = 86400, 7 * 86400
R_MIN, SH_MIN = 0.05, 0.20
PER = {"2020–2022": ("s88/oos2020_trades.pkl", "2020-10-01", "2022-10-01", "2021-10-01"),
       "2022–2024": ("s88/oos_trades.pkl", "2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("s88/trades.pkl", "2024-10-01", "2026-10-19", "2025-10-01")}
KRX_EXTRA = {                                   # закрытия KRX, которых нет среди праздников KR
    "2020-04-15", "2020-05-01", "2020-08-17", "2020-12-31",
    "2021-12-31",
    "2022-03-09", "2022-06-01", "2022-12-30",
    "2023-05-01", "2023-10-02", "2023-12-29",
    "2024-04-10", "2024-05-01", "2024-10-01", "2024-12-31",
    "2025-01-27", "2025-05-01", "2025-06-03", "2025-12-31",
    "2026-05-01", "2026-06-03", "2026-12-31"}


def daytype(t):
    """Тип дня по дате в Корее (вход ⏰ — 01:00 UTC = 10:00 KST): weekend / holiday / open."""
    kr = holidays.KR(years=range(2020, 2027))
    out = []
    for x in np.asarray(t, np.int64):
        d = (dt.datetime.utcfromtimestamp(int(x)) + dt.timedelta(hours=9)).date()
        if d.weekday() >= 5:
            out.append("weekend")
        elif d in kr or d.isoformat() in KRX_EXTRA:
            out.append("holiday")
        else:
            out.append("open")
    return np.array(out)


def load(per):
    f, a, b, mid = PER[per]
    X = pd.read_pickle(f)
    X = X[X.open9 & (X.r1 >= R_MIN) & (X.share >= SH_MIN)].copy()
    X = X[(X.t >= pd.Timestamp(a, tz="UTC").timestamp()) & (X.t < pd.Timestamp(b, tz="UTC").timestamp())]
    X["dt"] = daytype(X.t.values)
    X["closed"] = X.dt != "open"
    return X


def wk(t):
    return (np.asarray(t, np.int64) // WEEK) * WEEK


def ct(x, t):
    x = np.asarray(x, float); w = wk(t); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, m / se if se > 0 else np.nan, len(x)


def diff(y, d, t):
    """Разность средних d = 1 минус d = 0 с ошибкой, кластеризованной по неделям: (Δ, ошибка)."""
    y = np.asarray(y, float); d = np.asarray(d, float); t = np.asarray(t, float)
    m = ~np.isnan(y); y, d, t = y[m], d[m], t[m]
    if d.sum() < 5 or (1 - d).sum() < 5:
        return np.nan, np.nan
    Z = np.c_[np.ones(len(y)), d]; A = np.linalg.inv(Z.T @ Z); beta = A @ Z.T @ y; u = y - Z @ beta
    S = pd.DataFrame(Z * u[:, None]).groupby(wk(t)).sum().to_numpy(); G = len(S)
    V = A @ (S.T @ S) @ A * G / (G - 1)
    return float(beta[1]), float(np.sqrt(V[1, 1]))


def months(per):
    _, a, b, _ = PER[per]
    return (pd.Timestamp(b) - pd.Timestamp(a)).days / 30.44


def count():
    for per in PER:
        X = load(per)
        c = X.dt.value_counts()
        print(f"{per}: сделок ⏰ {len(X)} ({len(X) / months(per):.1f} в месяц) | выходные {c.get('weekend', 0)}, "
              f"праздники и закрытия KRX {c.get('holiday', 0)}, рабочие дни KRX {c.get('open', 0)} | "
              f"KRX закрыта — {X.closed.sum() / months(per):.1f} в месяц")


def line(x, per, col="S_10_25"):
    m, t, n = ct(x[col], x.t)
    md, td, _ = ct(x[col] - x["pl_" + col], x.t)
    _, a, b, mid = PER[per]
    cut = pd.Timestamp(mid, tz="UTC").timestamp()
    return (f"n={n} ({n / months(per):.1f} в месяц), {m:+.2%} (t по неделям {t:+.1f}); половины {x[x.t < cut][col].mean():+.2%} / "
            f"{x[x.t >= cut][col].mean():+.2%}; сверх плацебо {md:+.2%} (t {td:+.1f})")


def main():
    parts = []
    for per in PER:
        X = load(per)
        print(f"== {per}")
        print(f"  ⏰ все: {line(X, per)}")
        print(f"  KRX закрыта: {line(X[X.closed], per)}")
        print(f"  KRX работает: {line(X[~X.closed], per)}")
        print(f"  только выходные: {line(X[X.dt == 'weekend'], per)}")
        h = X[X.dt == "holiday"]
        print(f"  только праздники и закрытия KRX в будни: {line(h, per) if len(h) >= 5 else f'n={len(h)}, {h.S_10_25.mean():+.2%}'}")
        d, se = diff(X.S_10_25, X.closed.astype(float), X.t)
        print(f"  Δ (закрыта − работает): {d:+.2%} (t {d / se:+.1f})")
        parts.append((per, d, se, len(X)))
    ind = [(d, se, n) for per, d, se, n in parts if per != "2024–2026"]
    W = sum(n for *_, n in ind)
    m = sum(d * n for d, _, n in ind) / W
    se = np.sqrt(sum((s * n) ** 2 for _, s, n in ind)) / W
    print(f"\nДва независимых периода (2020–2022, 2022–2024) вместе: Δ {m:+.2%} (t {m / se:+.1f})")
    ok = all(d > 0 for per, d, se, n in parts if per != "2024–2026") and m / se >= 2
    print("порог s254 (Δ > 0 в обоих независимых периодах и вместе t ≥ 2):", "пройден" if ok else "не пройден")
    allp = [(d, se, n) for _, d, se, n in parts]
    W = sum(n for *_, n in allp); m3 = sum(d * n for d, _, n in allp) / W
    se3 = np.sqrt(sum((s * n) ** 2 for _, s, n in allp)) / W
    print(f"Три периода вместе (для отчёта): Δ {m3:+.2%} (t {m3 / se3:+.1f})")


if __name__ == "__main__":
    {"count": count, "main": main}[sys.argv[1] if len(sys.argv) > 1 else "count"]()
