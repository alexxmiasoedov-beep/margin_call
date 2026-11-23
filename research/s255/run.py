"""s255 — пампы в выходные (ключ s254: ⏰ в выходные сильнее во всех трёх периодах). Правило проверки — ВЫВОДЫ.md,
записано до расчёта. Пампы трёх периодов — s132_pumps.pkl (из файлов s119: +15% за ≤ 2 ч из покоя, шорт на закрытии
свечи пампа, тейк 10 / стоп 25 / 48 ч, одна сделка на монету за 48 ч). Плацебо на 2024–2026 гг. — та же сделка у той же
монеты за 45/90/135 сут (s15/common.trade, свечи s2/k2y.pkl).
Запуск из /home/user/mc_data: python3 <repo>/research/s255/run.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
DAY, WEEK = 86400, 7 * 86400
MO = {"10.2020–09.2022": 24.0, "10.2022–09.2024": 24.0, "10.2024–10.2026": 24.6}
MID = {"10.2020–09.2022": "2021-10-01", "10.2022–09.2024": "2023-10-01", "10.2024–10.2026": "2025-10-01"}


def wk(t):
    return (np.asarray(t, np.int64) // WEEK) * WEEK


def ct(x, t):
    x = np.asarray(x, float); w = wk(t); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, m / se if se > 0 else np.nan, len(x)


def diff(y, d, t):
    y = np.asarray(y, float); d = np.asarray(d, float); t = np.asarray(t, float)
    m = ~np.isnan(y); y, d, t = y[m], d[m], t[m]
    Z = np.c_[np.ones(len(y)), d]; A = np.linalg.inv(Z.T @ Z); beta = A @ Z.T @ y; u = y - Z @ beta
    S = pd.DataFrame(Z * u[:, None]).groupby(wk(t)).sum().to_numpy(); G = len(S)
    V = A @ (S.T @ S) @ A * G / (G - 1)
    return float(beta[1]), float(np.sqrt(V[1, 1]))


def line(x, per, col="net"):
    m, t, n = ct(x[col], x.t)
    cut = pd.Timestamp(MID[per], tz="UTC").timestamp()
    s = f"n={n} ({n / MO[per]:.1f} в месяц), {m:+.2%} (t по неделям {t:+.1f}); половины {x[x.t < cut][col].mean():+.2%} / {x[x.t >= cut][col].mean():+.2%}"
    if "pl" in x and x.pl.notna().any():
        md, td, _ = ct(x[col] - x.pl, x.t)
        s += f"; сверх плацебо {md:+.2%} (t {td:+.1f}), плацебо есть у {x.pl.notna().mean():.0%}"
    return s


def placebo(X):
    from common import K, trade  # noqa: E402
    pl, chk = [], []
    for r in X.itertuples():
        a = K.get(r.s)
        if a is None:
            pl.append(np.nan); continue
        t = a["t"].astype(np.int64)
        i0 = int(np.searchsorted(t, int(r.t) - 900))                    # t в таблице — закрытие свечи входа
        if len(chk) < 200 and i0 < len(t) and t[i0] == int(r.t) - 900:     # сверка соглашения о времени входа
            z = trade(r.s, i0, 0.10, 0.25, 48)
            if z is not None:
                chk.append(abs(z["net"] - r.net) < 1e-6)
        v = []
        for d in (45, 90, 135):
            tt = int(r.t) - 900 - d * DAY
            i = int(np.searchsorted(t, tt))
            if i < len(t) and t[i] == tt:
                z = trade(r.s, i, 0.10, 0.25, 48)
                if z is not None:
                    v.append(z["net"])
        pl.append(np.mean(v) if v else np.nan)
    print(f"сверка входа (пересчёт сделки пампа совпал): {np.mean(chk):.0%} из {len(chk)}")
    return np.array(pl)


def main():
    X = pd.read_pickle("s132_pumps.pkl")[["s", "t", "net", "per"]].copy()
    X = X[X.net.notna()]
    d = pd.to_datetime(X.t, unit="s", utc=True)
    X["we"] = (d.dt.weekday >= 5).values
    h = d.dt.hour + d.dt.minute / 60
    X["cme"] = (((d.dt.weekday == 4) & (h >= 21)) | (d.dt.weekday == 5) | ((d.dt.weekday == 6) & (h < 22))).values
    X["sat"] = (d.dt.weekday == 5).values
    parts = []
    for per, g in X.groupby("per", sort=False):
        if per == "10.2024–10.2026":
            g = g.copy(); g["pl"] = placebo(g)
        print(f"== {per}")
        print(f"  выходные UTC: {line(g[g.we], per)}")
        print(f"  будни: {line(g[~g.we], per)}")
        dd, se = diff(g.net, g.we.astype(float), g.t)
        print(f"  Δ выходные − будни: {dd:+.2%} (t {dd / se:+.1f})")
        print(f"  окно закрытого CME (пт 21:00 – вс 22:00 UTC): {line(g[g.cme], per)}")
        print(f"  суббота: {line(g[g.sat], per)} | воскресенье: {line(g[g.we & ~g.sat], per)}")
        parts.append((per, g[g.we].net.mean(), dd, se, len(g)))
        if per == "10.2024–10.2026":
            x = g[g.we]
            m, t, n = ct(x.net, x.t)
            cut = pd.Timestamp(MID[per], tz="UTC").timestamp()
            h1, h2 = x[x.t < cut].net.mean(), x[x.t >= cut].net.mean()
            md = (x.net - x.pl).mean()
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
                  (("≥ 20 в месяц", n / MO[per] >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                   ("сверх плацебо > 0", md > 0))))
    W = sum(n for *_, n in parts)
    m = sum(dd * n for _, _, dd, _, n in parts) / W
    se = np.sqrt(sum((s * n) ** 2 for _, _, _, s, n in parts)) / W
    ok = all(wm > 0 and dd > 0 for _, wm, dd, _, _ in parts) and m / se >= 2
    print(f"\nТри периода вместе: Δ {m:+.2%} (t {m / se:+.1f})")
    print("порог s255 (в каждом периоде выходные > 0 и Δ > 0, вместе t ≥ 2):", "пройден" if ok else "не пройден")


if __name__ == "__main__":
    main()
