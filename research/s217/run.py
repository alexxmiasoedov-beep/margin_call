"""s217 — займ к обороту (bqv) и выбранный пул (lim) на входе сделок журналов (гипотезы — ВЫВОДЫ.md, записаны до расчёта,
коммит b46d228). Сделки — s96/portfolio.load (бэктесты). Запуск из /home/user/mc_data: python3 <repo>/research/s217/run.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s96", "s216"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from portfolio import load  # noqa: E402
import features as F216  # noqa: E402  (K, rate_features)

H, DAY, WEEK = 3600, 86400, 7 * 86400
T0, T1 = pd.Timestamp("2025-02-20", tz="UTC").timestamp(), pd.Timestamp("2026-10-19", tz="UTC").timestamp()
MID = pd.Timestamp("2025-12-20", tz="UTC").timestamp()
SHORT = ("🇰🇷", "🛒", "🔝", "👀", "⏰", "📘", "🌊")
WEEKLY = ("🏦", "📢", "🇰🇷🆕", "🆕")


def ct_diff(y, g, t):
    """Разница средних (g = 1 против 0) и t по кластерам-неделям."""
    y, g, t = np.asarray(y, float), np.asarray(g, bool), np.asarray(t, np.int64)
    a, b = ~g, g
    if b.sum() < 5 or a.sum() < 5:
        return np.nan, np.nan, int(b.sum())
    ma, mb = y[a].mean(), y[b].mean()
    sa = pd.Series(y[a] - ma).groupby(t[a] // WEEK).sum() / a.sum()
    sb = pd.Series(y[b] - mb).groupby(t[b] // WEEK).sum() / b.sum()
    se = np.sqrt((sb.sub(sa, fill_value=0) ** 2).sum())
    return mb - ma, (mb - ma) / se, int(b.sum())


def main():
    X = load()
    X = X[(X.t >= T0) & (X.t < T1) & X.j.isin(SHORT + WEEKLY)].reset_index(drop=True)
    D = pd.read_pickle("s21/panel.pkl")
    key = {(s, int(T)): b for s, T, b in zip(D.s, D["T"], D.bor)}
    X["T"] = (X.t // H * H).astype(np.int64)
    X["bor"] = [key.get((s, T), np.nan) for s, T in zip(X.s, X["T"])]
    qv = []
    for s, t in zip(X.s, X.t):
        a = F216.K.get(s)
        if a is None:
            qv.append(np.nan); continue
        tt = a["t"].astype(np.int64) + 900
        i = int(np.searchsorted(tt, t, "right")) - 1
        qv.append(float(a["qv"][i - 95:i + 1].sum()) if i >= 96 else np.nan)
    X["qv24"] = qv
    X["bqv"] = X.bor / X.qv24.where(X.qv24 > 0)
    G = X[["s", "T"]].copy()
    X["lim"] = F216.rate_features(G)["lim"]
    X["inch"] = X.bor.notna()
    X["rd"] = X.r - X.groupby("j").r.transform("mean")             # доход минус среднее своего журнала
    X.to_pickle("s217_trades.pkl")
    months = (T1 - T0) / (30.44 * DAY)
    print(f"Сделок {len(X)} (короткие журналы {X.j.isin(SHORT).sum()}, недельные {X.j.isin(WEEKLY).sum()}); монета в канале на входе: "
          f"{X.inch.mean():.0%}; bqv ≥ 0,2: {int((X.bqv >= 0.2).sum())}; lim = 1: {int((X.lim == 1).sum())}\n")
    for grp, js in (("короткие (до 48 ч)", SHORT), ("недельные", WEEKLY)):
        Y = X[X.j.isin(js)]
        print(f"== {grp}: сделок {len(Y)}, в канале {Y.inch.mean():.0%}")
        for nm, g in (("Г1 bqv ≥ 0,2", Y.bqv >= 0.2), ("Г2 lim = 1", Y.lim == 1), ("в канале (для отчёта)", Y.inch)):
            d, t, n = ct_diff(Y.rd, g, Y.t)
            h = [ct_diff(Y.rd[m], g[m], Y.t[m])[0] for m in (Y.t < MID, Y.t >= MID)]
            print(f"  {nm}: сделок {n} ({n / months:.1f} в месяц), их доход {Y.r[g].mean():+.2%} против {Y.r[~g].mean():+.2%}; "
                  f"разница к среднему журнала {d:+.2%} (t по неделям {t:+.1f}); половины {h[0]:+.2%} / {h[1]:+.2%}")
        Z = Y[Y.inch & Y.bqv.notna()]
        if len(Z) >= 50:
            e = np.quantile(Z.bqv, [0.2, 0.4, 0.6, 0.8])
            q = np.searchsorted(e, Z.bqv, "right")
            print("  квинтили bqv среди сделок в канале (доход минус среднее журнала): "
                  + " | ".join(f"Q{k + 1} {Z.rd[q == k].mean():+.2%} (n {int((q == k).sum())})" for k in range(5))
                  + f"; границы {', '.join(f'{x:.3f}' for x in e)}")
        for j in js:
            y = Y[Y.j == j]
            if not len(y):
                continue
            v = y.bqv >= 0.2
            print(f"    {j}: сделок {len(y)}, в канале {y.inch.mean():.0%}, bqv ≥ 0,2 — {int(v.sum())} по {y.r[v].mean():+.2%} "
                  f"(остальные {y.r[~v].mean():+.2%}); итог журнала {y.r.sum():+.1f} → без них {y.r[~v].sum():+.1f} (в долях сделки)")
        print()


if __name__ == "__main__":
    main()
