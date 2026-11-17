"""s77 — продолжение большого хода за двое суток (гипотеза — ВЫВОДЫ.md, записана до расчёта). Каждый день в 21:00 UTC:
ход монеты за 48 ч к медиане вселенной (криптофьючерсы ≥ 30 сут, медианный суточный оборот за 30 сут ≥ 5 млн $);
≥ +10% → лонг (основной), ≤ −10% → шорт (зеркало); одно событие на монету и сторону за 48 ч; выход 48 ч (основной)
или 24 ч, стоп 20%, без тейка; плацебо — та же монета за 45/90/135 сут. Запуск из папки с данными."""
import datetime
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s23", "s76"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from common23 import TRADFI  # noqa: E402
from wk_test import close_idx, dvol  # noqa: E402

UTC = datetime.timezone.utc
THR = 0.10


def main():
    syms = [s for s in K if s not in TRADFI]
    DV = {s: dvol(s) for s in syms}
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    other = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        other.setdefault(s, []).append(t)
    other = {s: np.array(v) for s, v in other.items()}
    rows, last = [], {}
    d = datetime.date(2024, 11, 10)
    while d <= datetime.date(2026, 10, 15):
        E = int(datetime.datetime(d.year, d.month, d.day, 21, tzinfo=UTC).timestamp()); C = E - 2 * DAY
        cand = []
        for s in syms:
            lo, hi = live(s)
            if C < lo + 30 * DAY or E + 2 * DAY > hi:
                continue
            dv = DV[s]; dd = dv[(dv.index >= C - 30 * DAY) & (dv.index < C - DAY)]
            if len(dd) < 20 or dd.median() < 5e6:
                continue
            i0, i = close_idx(s, C), close_idx(s, E)
            if i0 is None or i is None:
                continue
            c = K[s]["c"]; cand.append((s, float(c[i] / c[i0] - 1), i))
        if cand:
            med = np.median([r for _, r, _ in cand])
            for s, r, i in cand:
                rel = r - med
                if abs(rel) < THR:
                    continue
                side = 1 if rel > 0 else -1
                if E - last.get((s, side), -1e18) < 2 * DAY:
                    continue
                last[(s, side)] = E
                o = other.get(s, np.zeros(0))
                row = dict(s=s, t=E, rel=rel, side=side, wd=d.weekday(), ov=bool(((o < E) & (o >= E - 2 * DAY)).any()))
                for nm, h in (("n48", 48), ("n24", 24)):
                    x = trade(s, i, tp=None, sl=0.20, hold_h=h, side=side)
                    row[nm] = x["net"] if x else np.nan
                    p = []
                    for dd_ in (45, 90, 135):
                        T2 = E - dd_ * DAY; j = close_idx(s, T2)
                        if j is not None and T2 >= live(s)[0] and (y := trade(s, j, tp=None, sl=0.20, hold_h=h, side=side)):
                            p.append(y["net"])
                    row["pl_" + nm] = np.mean(p) if p else np.nan
                rows.append(row)
        d += datetime.timedelta(1)
    X = pd.DataFrame(rows)
    X.to_pickle("s77/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    L = X[X.side > 0]
    print(f"Событий: лонг {len(L)} ({len(L) / months:.1f} в месяц), шорт {len(X) - len(L)}; у лонга вход 🛒 🔝 🇰🇷 за 48 ч: {L.ov.mean():.0%}")
    groups = [("лонг лидеров (основная)", L), ("лонг без окон вт → чт", L[L.wd != 3]), ("лонг, только вт → чт", L[L.wd == 3]),
              ("лонг без 🛒 🔝 🇰🇷", L[~L.ov]), ("шорт отстающих (зеркало)", X[X.side < 0])]
    for lab, x0 in groups:
        for col in ("n48", "n24"):
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:26s} {col} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
