"""s80 — шорт на неделю после кластера ликвидаций (гипотеза — ВЫВОДЫ.md, записана до расчёта). События — как в s72
(ликвидации одной стороны за час ≥ 0,25 медианного часового оборота за 7 сут; без BTC, ETH и не крипто; фьючерс ≥ 30 сут),
стороны вместе, одно событие на монету за 7 сут. Шорт на закрытии часа H + 24 ч (основной) или сразу (свеча H … H + 15 мин),
7 сут, стоп 50%, без тейка; плацебо — та же монета за 45/90/135 сут с тем же сдвигом. Запуск из папки с данными."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s22", "s72"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from liq_test import entry, events, posts  # noqa: E402

KW = dict(tp=None, sl=0.50, hold_h=168)


def main():
    E = events(posts())
    E = E[E.x >= 0.25].sort_values("t")
    keep, last = [], {}
    for r in E.itertuples():
        if r.t - last.get(r.s, -1e18) >= 7 * DAY:
            last[r.s] = r.t; keep.append(r.Index)
    E = E.loc[keep]
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    other = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        other.setdefault(s, []).append(t)
    other = {s: np.array(v) for s, v in other.items()}
    rows = []
    for r in E.itertuples():
        lo, hi = live(r.s)
        if r.t + DAY + 8 * DAY > hi:
            continue
        o = other.get(r.s, np.zeros(0))
        d = dict(s=r.s, t=r.t, side=r.side, x=r.x, ov=bool(((o < r.t) & (o >= r.t - DAY)).any()))
        for nm, off in (("late", DAY), ("now", 0)):
            i = entry(r.s, r.t + off)
            x = trade(r.s, i, side=-1, **KW) if i is not None else None
            d[nm] = x["net"] if x else np.nan
            p = []
            for dd in (45, 90, 135):
                T2 = r.t + off - dd * DAY; j = entry(r.s, T2)
                if j is not None and T2 >= lo and (y := trade(r.s, j, side=-1, **KW)):
                    p.append(y["net"])
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s80/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий {len(X)} ({len(X) / months:.1f} в месяц): ликвидированы лонги {(X.side == 'Long').sum()},"
          f" шорты {(X.side == 'Short').sum()}; с 🛒 🔝 🇰🇷 за 24 ч: {X.ov.mean():.0%}")
    for lab, x0 in (("обе стороны", X), ("лонги ликвидированы", X[X.side == "Long"]), ("шорты ликвидированы", X[X.side == "Short"])):
        for col, nm in (("late", "через сутки (основная)" if lab == "обе стороны" else "через сутки"), ("now", "сразу")):
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:20s} {nm:24s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
