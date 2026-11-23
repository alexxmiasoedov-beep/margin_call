"""s257 — розничный памп в выходные (ключ s254–s255): шорт пампов с долей спота Binance ≥ 26% или долей Кореи ≥ 20%,
вход в субботу или воскресенье UTC. Правило проверки — ВЫВОДЫ.md, записано до расчёта. Пампы трёх периодов — файлы
s119 (+15% за ≤ 2 ч из покоя, шорт на закрытии свечи пампа 10/25/48 ч, одна сделка на монету за 48 ч; доля спота
share, доля Кореи kr — в 2020–2022 гг. корейских данных нет). Плацебо на 2024–2026 гг. — та же сделка у той же монеты за
45/90/135 сут (s15/common.trade; t в таблицах — закрытие свечи входа, как установлено в s255).
Запуск из /home/user/mc_data: python3 <repo>/research/s257/run.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
DAY, WEEK = 86400, 7 * 86400
F = {"2020–2022": ("/home/user/mc_2020/s119_y2020.pkl", 24.0, "2021-10-01"),
     "2022–2024": ("/home/user/mc_oos/s119_old.pkl", 24.0, "2023-10-01"),
     "2024–2026": ("/home/user/mc_data/s119_new.pkl", 24.6, "2025-10-01")}


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


def line(x, per):
    _, mo, mid = F[per]
    m, t, n = ct(x.net, x.t)
    if n < 5:
        return f"n={n}"
    cut = pd.Timestamp(mid, tz="UTC").timestamp()
    s = (f"n={n} ({n / mo:.1f} в месяц), {m:+.2%} (t по неделям {t:+.1f}); половины {x[x.t < cut].net.mean():+.2%} / "
         f"{x[x.t >= cut].net.mean():+.2%}; стопов {(x.net <= -0.25).mean():.0%}")
    if "pl" in x and x.pl.notna().any():
        md, td, _ = ct(x.net - x.pl, x.t)
        s += f"; сверх плацебо {md:+.2%} (t {td:+.1f}), плацебо у {x.pl.notna().mean():.0%}"
    return s


def placebo(X):
    from common import K, trade  # noqa: E402
    out = []
    for r in X.itertuples():
        a = K.get(r.s)
        if a is None:
            out.append(np.nan); continue
        t = a["t"].astype(np.int64); v = []
        for d in (45, 90, 135):
            tt = int(r.t) - 900 - d * DAY
            i = int(np.searchsorted(t, tt))
            if i < len(t) and t[i] == tt:
                z = trade(r.s, i, 0.10, 0.25, 48)
                if z is not None:
                    v.append(z["net"])
        out.append(np.mean(v) if v else np.nan)
    return np.array(out)


def main():
    parts = []
    for per, (f, mo, mid) in F.items():
        X = pd.read_pickle(f)
        X = X[X.net.notna()].copy()
        d = pd.to_datetime(X.t, unit="s", utc=True)
        X["we"] = (d.dt.weekday >= 5).values
        X["o9"] = ((d.dt.hour == 0) | ((d.dt.hour == 1) & (d.dt.minute <= 15))).values      # окно ⏰
        sp = (X.share >= 0.26).fillna(False)
        kr = (X.kr >= 0.20).fillna(False) if "kr" in X else pd.Series(False, index=X.index)
        X["sp"], X["krf"] = sp.values, kr.values
        R = X[X.sp | X.krf].copy()
        if per == "2024–2026":
            R["pl"] = placebo(R)
        W, D = R[R.we], R[~R.we]
        dd, se = diff(R.net, R.we.astype(float), R.t)
        print(f"== {per}")
        print(f"  розничные пампы в выходные: {line(W, per)}")
        print(f"  розничные пампы в будни: {line(D, per)}")
        print(f"  Δ выходные − будни: {dd:+.2%} (t {dd / se:+.1f})")
        print(f"  выходные, доля спота ≥ 26%: {line(W[W.sp], per)}")
        print(f"  выходные, доля Кореи ≥ 20%: {line(W[W.krf], per)}")
        print(f"  выходные без окна ⏰ (вход не в 00:00–01:15 UTC): {line(W[~W.o9], per)}")
        print(f"  все пампы в выходные (для сравнения, s255): {line(X[X.we], per)}")
        parts.append((per, W.net.mean(), dd, se, len(R)))
        if per == "2024–2026":
            m, t, n = ct(W.net, W.t)
            cut = pd.Timestamp(mid, tz="UTC").timestamp()
            h1, h2 = W[W.t < cut].net.mean(), W[W.t >= cut].net.mean()
            md = (W.net - W.pl).mean()
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
                  (("≥ 20 в месяц", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                   ("сверх плацебо > 0", md > 0))))
    Wt = sum(n for *_, n in parts)
    m = sum(dd * n for _, _, dd, _, n in parts) / Wt
    se = np.sqrt(sum((s * n) ** 2 for _, _, _, s, n in parts)) / Wt
    ok = all(wm > 0 and dd > 0 for _, wm, dd, _, _ in parts) and m / se >= 2
    print(f"\nТри периода вместе: Δ {m:+.2%} (t {m / se:+.1f})")
    print("порог s257 (в каждом периоде выходные > 0 и Δ > 0, вместе t ≥ 2):", "пройден" if ok else "не пройден")


if __name__ == "__main__":
    main()
