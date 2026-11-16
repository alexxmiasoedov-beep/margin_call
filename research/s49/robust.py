"""s49 — устойчивость основного правила (верхняя треть доли спота Binance в пампе → шорт 10/25/48) после того, как оно
прошло порог. Кварталы и месяцы; выходы S_7_20, S_10_15, 7 сут со стопом 50%; вход на свечу позже (закрытие следующей
15-мин свечи); пороги доли 20–40%; без лучших сделок и монет; пересечение с сигналами журналов (s44.consensus.signals)
в ±12 ч. Запуск из папки с данными после spot_test.py."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s44"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

Q2 = 0.259                                                     # граница верхней трети по первой половине (spot_test.py)
EXITS = {"10/25/48 (основной)": dict(tp=0.10, sl=0.25, hold_h=48), "S_7_20": dict(tp=0.07, sl=0.20, hold_h=48),
         "S_10_15": dict(tp=0.10, sl=0.15, hold_h=24), "7 сут, стоп 50%": dict(tp=None, sl=0.50, hold_h=168)}


def j_of(s, t):
    return int(np.searchsorted(K[s]["t"], t - 900))


def stat(x, col="net"):
    m, t, n = ct(x[col], x.t)
    a, b = x[x.t < CUT][col].mean(), x[x.t >= CUT][col].mean()
    return f"n={n:4d} {m:+6.2%} (t {t:+4.1f}) | половины {a:+6.2%} / {b:+6.2%} | в плюсе {(x[col] > 0).mean():3.0%}"


def main():
    X = pd.read_pickle("s49/trades.pkl")
    M = X[X.share >= Q2].copy()
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Основное правило: {len(M)} сделок, {len(M) / months:.1f} в месяц, монет {M.s.nunique()}")
    M["q"] = pd.to_datetime(M.t, unit="s").dt.to_period("Q").astype(str)
    M["m"] = pd.to_datetime(M.t, unit="s").dt.to_period("M").astype(str)
    print("\nПо кварталам: " + " | ".join(f"{q}: {len(g)} {g.net.mean():+.1%}" for q, g in M.groupby("q")))
    mm = M.groupby("m").net.sum()
    print(f"Месяцев в плюсе: {(mm > 0).sum()} из {len(mm)}; худший месяц {mm.min():+.2f}, лучший {mm.max():+.2f} (сумма долей)")

    print("\nВыходы и вход на свечу позже:")
    for nm, kw in EXITS.items():
        for lag in (0, 1):
            v = []
            for r in M.itertuples():
                x = trade(r.s, j_of(r.s, r.t) + lag, **kw)
                v.append(x["net"] if x else np.nan)
            y = M.assign(v=v).dropna(subset=["v"])
            print(f"  {nm:22s} вход {'на закрытии пампа' if lag == 0 else 'на свечу позже  '}: {stat(y, 'v')}")

    print("\nПороги доли спота (основной выход):")
    for thr in (0.20, 0.225, 0.259, 0.30, 0.35, 0.40):
        y = X[X.share >= thr]
        print(f"  доля ≥ {thr:.1%}: {len(y) / months:5.1f} в месяц | {stat(y)}")

    print("\nБез лучших:")
    srt = M.sort_values("net", ascending=False)
    for k in (10, 20, 50):
        y = srt.iloc[k:]
        print(f"  без {k} лучших сделок: {stat(y)}")
    top = M.groupby("s").net.sum().sort_values(ascending=False)
    for k in (5, 10):
        y = M[~M.s.isin(top.index[:k])]
        print(f"  без {k} самых прибыльных монет: {stat(y)}")

    print("\nПересечение с журналами (сигнал журнала по той же монете в ±12 ч):")
    import consensus
    S = consensus.signals()
    by = {s: g.t.values for s, g in S.groupby("s")}
    js = {s: g.j.values for s, g in S.groupby("s")}
    hit, who = [], []
    for r in M.itertuples():
        tt = by.get(r.s, np.zeros(0)); w = np.abs(tt - r.t) <= 12 * 3600
        hit.append(bool(w.any())); who.append(",".join(sorted(set(js[r.s][w]))) if w.any() else "")
    M["hit"], M["who"] = hit, who
    print(f"  с сигналом журнала: {M.hit.mean():.0%} — {stat(M[M.hit])}")
    print(f"  без сигналов журналов: {stat(M[~M.hit])} ({(~M.hit).sum() / months:.1f} в месяц)")
    print("  какие журналы: " + str(pd.Series([w for s in M[M.hit].who for w in s.split(',')]).value_counts().to_dict()))


if __name__ == "__main__":
    main()
