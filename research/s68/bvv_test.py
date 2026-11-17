"""s68 — пик внимания европейской розницы на Bitvavo (гипотеза — ВЫВОДЫ.md, записана до скачивания). Часовой оборот X-EUR
(s68/bvv1h.pkl) по фьючерсам Binance; сумма за 24 ч; 10 лидеров первой половины и стейблкоины не считаются; монета впервые
за 7 сут в пятёрке, фьючерс старше суток → шорт 10/25/48 (основной) и 7 сут со стопом 50%; одна сделка на монету за 7 сут;
плацебо — та же монета за 45/90/135 сут; пересечение — входы 🔝 (s65), 🛒 (s49), 🇰🇷 (s20) за прошлые 24 ч.
Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s66"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import fut_of  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from attn_test import EXITS, events, idx_at, trade  # noqa: E402

STABLE = {"USDT", "USDC", "EURC", "EURT", "DAI", "USDE", "PYUSD", "TUSD", "FDUSD", "USD1", "USDS", "RLUSD"}


def main():
    B = pickle.load(open("s68/bvv1h.pkl", "rb"))
    cols = {}
    for c, d in B.items():
        if c in STABLE:
            continue
        s, _ = fut_of(c)
        if s:
            v = d.set_index("T").eur
            cols[s] = cols[s].add(v, fill_value=0.0) if s in cols else v
    V = pd.DataFrame(cols)
    print(f"Фьючерсов с рынком на Bitvavo: {V.shape[1]}")
    ev, majors = events(V)
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    other = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        other.setdefault(s, []).append(t)
    other = {s: np.array(v) for s, v in other.items()}
    rows = []
    for s, T in ev:
        i = idx_at(s, T); o = other.get(s, np.zeros(0))
        d = dict(s=s, t=T, past=bool(((o < T) & (o >= T - DAY)).any()))
        for nm, kw in EXITS.items():
            x = trade(s, i, **kw)
            d[nm] = x["net"] if x else np.nan
            p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **kw))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s68/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Лидеры: {majors}\nСобытий: {len(X)} ({len(X) / months:.1f} в месяц), с прошлым сигналом 🔝 🛒 🇰🇷 за 24 ч: {X.past.mean():.0%}")
    for lab, x0 in (("все (основная)", X), ("без прошлых 🔝 🛒 🇰🇷", X[~X.past])):
        for col in EXITS:
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:22s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
