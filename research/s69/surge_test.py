"""s69 — всплеск корейского оборота ×10 против обычного у монеты (гипотеза — ВЫВОДЫ.md, записана до расчёта). Часовой оборот
Кореи — s15/kr_panel.pkl; сумма за 24 ч; обычный — медиана сумм за 24 ч на часах (T − 8 сут, T − 1 сут]. Событие: сумма ≥ 10×
обычного и ≥ 1 млн $, монета не из 10 лидеров 🔝, корейского листинга (s15/kr_journal.pkl) за прошлые 14 сут не было,
фьючерс старше суток; одно событие на монету за 7 сут. Шорт 10/25/48 (основной) и 7 сут со стопом 50%; плацебо — та же
монета за 45/90/135 сут; пересечение — входы 🔝, 🛒, 🇰🇷 за прошлые 24 ч. Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s66"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from attn_test import EXITS, idx_at, trade  # noqa: E402

MAJORS = {"XRP", "BTC", "ETH", "DOGE", "SOL", "SUI", "ONDO", "ADA", "WLD", "1000SHIB"}


def main():
    KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    LJ = pd.read_pickle("s15/kr_journal.pkl")
    lst = {s: g.t.values for s, g in LJ.groupby("sym")}
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    other = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        other.setdefault(s, []).append(t)
    other = {s: np.array(v) for s, v in other.items()}
    rows = []
    for s, d in KP.items():
        if s not in K or s in MAJORS:
            continue
        v = d.set_index("T").kr.sort_index()
        full = pd.Series(0.0, index=np.arange(int(v.index.min()), int(v.index.max()) + 3600, 3600))
        v = full.add(v, fill_value=0.0)
        v24 = v.rolling(24, min_periods=24).sum()
        norm = v24.shift(24).rolling(168, min_periods=120).median()            # часы (T − 8 сут, T − 1 сут]
        hit = (v24 >= 10 * norm) & (v24 >= 1e6) & (norm > 0)
        lo, hi = live(s); last = -1e18
        for T in v24.index[hit.values]:
            T = int(T)
            if T - last < 7 * DAY or T < lo + DAY or T > hi:
                continue
            L = lst.get(s, np.zeros(0))
            if ((L <= T) & (L >= T - 14 * DAY)).any():
                continue
            i = idx_at(s, T)
            if i is None:
                continue
            last = T
            o = other.get(s, np.zeros(0))
            r = dict(s=s, t=T, x=float(v24[T] / norm[T]), past=bool(((o < T) & (o >= T - DAY)).any()))
            for nm, kw in EXITS.items():
                x = trade(s, i, **kw)
                r[nm] = x["net"] if x else np.nan
                p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **kw))]
                r["pl_" + nm] = np.mean(p) if p else np.nan
            rows.append(r)
    X = pd.DataFrame(rows)
    X.to_pickle("s69/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий: {len(X)} ({len(X) / months:.1f} в месяц), с прошлым сигналом 🔝 🛒 🇰🇷 за 24 ч: {X.past.mean():.0%};"
          f" медиана всплеска ×{X.x.median():.0f}")
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
