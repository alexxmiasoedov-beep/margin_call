"""s66 — пик внимания на других площадках (гипотеза — ВЫВОДЫ.md, записана до расчёта): спот Binance (s23/spot1h.pkl),
фьючерсы Binance (s2/k2y.pkl), Coinbase (s46/cb1h.pkl). Для каждой: часовой оборот в $ → сумма за 24 ч; 10 лидеров по
медиане первой половины не считаются; событие — монета впервые за 7 сут в пятёрке, фьючерс Binance старше суток; шорт
10/25/48 (основной) и 7 сут со стопом 50%; одна сделка на монету за 7 сут; плацебо — та же монета за 45/90/135 сут;
пересечение с 🔝 (s65/trades.pkl) и 🛒 (s49) в ±24 ч. Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

EXITS = {"S_10_25": dict(tp=0.10, sl=0.25, hold_h=48), "S_7d": dict(tp=None, sl=0.50, hold_h=168)}


def hourly_spot():
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    return pd.DataFrame({s: pd.Series(a[:, 1], index=a[:, 0].astype(np.int64) + 3600) for s, a in SP.items() if s in K})


def hourly_perp():
    out = {}
    for s, a in K.items():
        Tend = a["t"].astype(np.int64) + 900
        out[s] = pd.Series(a["qv"].astype(float)).groupby(((Tend - 1) // 3600 + 1) * 3600).sum()
    return pd.DataFrame(out)


def hourly_cb():
    CB = pickle.load(open("s46/cb1h.pkl", "rb"))
    out = {}
    for b, d in CB.items():
        s, _ = fut_of(b)
        if s:
            out[s] = d.set_index("T").usd
    return pd.DataFrame(out)


def events(V):
    V = V.sort_index().fillna(0.0)
    V = V[(V.index >= pd.Timestamp("2024-10-01", tz="UTC").timestamp())]
    V24 = V.rolling(24, min_periods=24).sum().dropna(how="all")
    majors = list(V24[V24.index < CUT].median().sort_values(ascending=False).index[:10])
    R = V24.drop(columns=majors).rank(axis=1, ascending=False, method="first")
    top = R <= 5
    in7 = top.rolling(168, min_periods=1).max().shift(1).fillna(0).astype(bool)
    out, last = [], {}
    for T, row in top.iterrows():
        T = int(T)
        for s in row.index[row.values]:
            if in7.at[T, s] or T - last.get(s, -1e18) < 7 * DAY:
                continue
            lo, hi = live(s)
            if T < lo + DAY or T > hi or idx_at(s, T) is None:
                continue
            last[s] = T
            out.append((s, T))
    return out, majors


def main():
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    other = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S49.s, S49.t)):
        other.setdefault(s, []).append(t)
    other = {s: np.array(v) for s, v in other.items()}
    for name, V in (("спот Binance", hourly_spot()), ("фьючерсы Binance", hourly_perp()), ("Coinbase", hourly_cb())):
        ev, majors = events(V)
        rows = []
        for s, T in ev:
            i = idx_at(s, T)
            d = dict(s=s, t=T, ov=bool((np.abs(other.get(s, np.zeros(0)) - T) <= DAY).any()))
            for nm, kw in EXITS.items():
                x = trade(s, i, **kw)
                d[nm] = x["net"] if x else np.nan
                p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **kw))]
                d["pl_" + nm] = np.mean(p) if p else np.nan
            rows.append(d)
        X = pd.DataFrame(rows)
        X.to_pickle(f"s66/trades_{name.split()[0]}.pkl")
        months = (X.t.max() - X.t.min()) / (30.4 * DAY)
        print(f"\n## {name}: лидеры {majors}; событий {len(X)} ({len(X) / months:.1f} в месяц), с 🔝 или 🛒 в ±24 ч: {X.ov.mean():.0%}")
        for lab, x0 in (("все", X), ("без 🔝 и 🛒", X[~X.ov])):
            for col in EXITS:
                x = x0[x0[col].notna()]
                if len(x) < 8:
                    continue
                m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
                a, b = x[x.t < CUT][col].mean(), x[x.t >= CUT][col].mean()
                print(f"  {lab:12s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                      f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x['pl_' + col].mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
