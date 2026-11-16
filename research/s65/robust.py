"""s65 — устойчивость правила «монета входит в пятёрку по обороту Кореи за 24 ч → шорт 10/25/48» (второй записанный выход).
Пересечение с сигналами журналов (s44.consensus.signals, ±24 ч) и с 🛒 (s49); кварталы и месяцы; вход на час позже;
пороги пятёрки (3, 10); без лучших сделок и монет. Запуск из папки с данными после krtop_test.py."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s44"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

EX = dict(tp=0.10, sl=0.25, hold_h=48)


def stat(x, col="v"):
    x = x[x[col].notna()]
    m, t, n = ct(x[col], x.t)
    a, b = x[x.t < CUT][col].mean(), x[x.t >= CUT][col].mean()
    return f"n={n:4d} {m:+6.2%} (t {t:+4.1f}) | половины {a:+6.2%} / {b:+6.2%} | в плюсе {(x[col] > 0).mean():3.0%}"


def events(topn, majors, V24):
    R = V24.drop(columns=majors).rank(axis=1, ascending=False, method="first")
    top = R <= topn
    in7 = top.rolling(168, min_periods=1).max().shift(1).fillna(0).astype(bool)
    out, last = [], {}
    for T, row in top.iterrows():
        for s in row.index[row.values]:
            if in7.at[T, s] or T - last.get(s, -1e18) < 7 * DAY:
                continue
            lo, hi = live(s)
            if T < lo + DAY or T > hi or idx_at(s, T) is None:
                continue
            last[s] = T
            out.append((s, T))
    return out


def main():
    KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    V = pd.DataFrame({s: d.set_index("T").kr for s, d in KP.items() if s in K}).sort_index().fillna(0.0)
    V24 = V.rolling(24, min_periods=24).sum()
    majors = list(V24[V24.index < CUT].median().sort_values(ascending=False).index[:10])
    X = pd.read_pickle("s65/trades.pkl").rename(columns={"S_10_25": "v"})
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Основное (пятёрка, 10/25/48): {stat(X)}; {len(X) / months:.1f} в месяц, монет {X.s.nunique()}")

    import consensus
    S = consensus.signals()
    S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    sig = {s: g for s, g in S.groupby("s")}
    cart = {s: g.t.values for s, g in S49.groupby("s")}
    who, hit = [], []
    for r in X.itertuples():
        g = sig.get(r.s)
        w = set(g.j[(np.abs(g.t - r.t) <= DAY)]) if g is not None else set()
        if (np.abs(cart.get(r.s, np.zeros(0)) - r.t) <= DAY).any():
            w.add("🛒")
        who.append(",".join(sorted(w))); hit.append(bool(w))
    X["who"], X["hit"] = who, hit
    print(f"\nС сигналом журнала по монете в ±24 ч: {X.hit.mean():.0%} — {stat(X[X.hit])}")
    print(f"Без сигналов журналов: {stat(X[~X.hit])} ({(~X.hit).sum() / months:.1f} в месяц)")
    print("Какие журналы:", pd.Series([w for s in X[X.hit].who for w in s.split(",")]).value_counts().to_dict())

    X["q"] = pd.to_datetime(X.t, unit="s").dt.to_period("Q").astype(str)
    print("\nПо кварталам: " + " | ".join(f"{q}: {len(g)} {g.v.mean():+.1%}" for q, g in X.groupby("q")))
    mm = X.groupby(pd.to_datetime(X.t, unit="s").dt.to_period("M")).v.sum()
    print(f"Месяцев в плюсе: {(mm > 0).sum()} из {len(mm)}")

    late = []
    for r in X.itertuples():
        i = idx_at(r.s, r.t + 3600)
        x = trade(r.s, i, **EX) if i is not None else None
        late.append(x["net"] if x else np.nan)
    print(f"\nВход на час позже: {stat(X.assign(v=late))}")

    for topn in (3, 10):
        ev = events(topn, majors, V24)
        v = [(lambda x: x["net"] if x else np.nan)(trade(s, idx_at(s, T), **EX)) for s, T in ev]
        Y = pd.DataFrame(dict(s=[e[0] for e in ev], t=[e[1] for e in ev], v=v))
        print(f"Порог — {topn} лучших: {len(Y) / months:.1f} в месяц | {stat(Y)}")

    srt = X.sort_values("v", ascending=False)
    print(f"\nБез 20 лучших сделок: {stat(srt.iloc[20:])}")
    topc = X.groupby("s").v.sum().sort_values(ascending=False).index[:10]
    print(f"Без 10 самых прибыльных монет: {stat(X[~X.s.isin(topc)])}")


if __name__ == "__main__":
    main()
