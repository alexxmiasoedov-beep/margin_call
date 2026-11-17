"""s76 — откат хода выходных у альткоинов (гипотеза — ВЫВОДЫ.md, записана до расчёта). Ход к рынку: пятница 21:00 →
воскресенье 21:00 UTC минус медиана вселенной (криптофьючерсы ≥ 30 сут, медианный суточный оборот за 30 сут ≥ 5 млн $).
|ход| ≥ 10% → сделка против хода с закрытия свечи в воскресенье 21:00, выход через 48 ч (основной) или 24 ч, стоп 20%.
Плацебо — та же монета в ту же неделю: вторник 21:00 → четверг 21:00, тот же порог, выход через 48 ч; отдельно — все
такие события середины недели. Запуск из папки с данными."""
import datetime
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s23"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from common23 import TRADFI  # noqa: E402

UTC = datetime.timezone.utc
THR = 0.10


def close_idx(s, T):
    t = K[s]["t"]; i = int(np.searchsorted(t, T - 900))
    return i if i < len(t) and t[i] == T - 900 and K[s]["qv"][i] > 0 else None


def dvol(s):
    a = K[s]; d = (a["t"].astype(np.int64) // DAY) * DAY
    return pd.Series(a["qv"].astype(float)).groupby(d).sum()


def window(C, E, X, DV, syms):
    """События окна C → E: монеты вселенной с |ход к рынку| ≥ THR; сделки против хода с E на X − E (48 ч) и 24 ч."""
    rows = []
    for s in syms:
        lo, hi = live(s)
        if C < lo + 30 * DAY or X > hi:
            continue
        dv = DV[s]; dd = dv[(dv.index >= C - 30 * DAY) & (dv.index < C - DAY)]
        if len(dd) < 20 or dd.median() < 5e6:
            continue
        i0, i = close_idx(s, C), close_idx(s, E)
        if i0 is None or i is None:
            continue
        c = K[s]["c"]
        rows.append((s, float(c[i] / c[i0] - 1), i))
    if not rows:
        return []
    med = np.median([r[1] for r in rows])
    out = []
    for s, r, i in rows:
        rel = r - med
        if abs(rel) < THR:
            continue
        side = -1 if rel > 0 else 1
        x48 = trade(s, i, tp=None, sl=0.20, hold_h=(X - E) / 3600, side=side)
        x24 = trade(s, i, tp=None, sl=0.20, hold_h=24, side=side)
        out.append(dict(s=s, t=E, rel=rel, side=side, n48=x48["net"] if x48 else np.nan, n24=x24["net"] if x24 else np.nan))
    return out


def main():
    syms = [s for s in K if s not in TRADFI]
    DV = {s: dvol(s) for s in syms}
    ev, mid = [], []
    fri = datetime.date(2024, 11, 8)
    while fri <= datetime.date(2026, 10, 9):
        C = int(datetime.datetime(fri.year, fri.month, fri.day, 21, tzinfo=UTC).timestamp())
        ev += window(C, C + 2 * DAY, C + 4 * DAY, DV, syms)
        mid += window(C - 3 * DAY, C - DAY, C + DAY, DV, syms)              # вторник 21:00 → четверг → суббота
        fri += datetime.timedelta(7)
    X = pd.DataFrame(ev); M = pd.DataFrame(mid)
    M["wk"] = M.t + 3 * DAY                                               # к воскресенью той же недели
    pl = M.set_index(["s", "wk"]).n48
    X["pl"] = [pl.get((s, t), np.nan) for s, t in zip(X.s, X.t)]
    X.to_pickle("s76/trades.pkl"); M.to_pickle("s76/mid.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий выходных {len(X)} ({len(X) / months:.1f} в месяц), выходных {X.t.nunique()}; событий середины недели {len(M)};"
          f" с парным плацебо {X.pl.notna().sum()}")
    for lab, x0 in (("все (основная)", X), ("шорт обогнавших", X[X.side < 0]), ("лонг отставших", X[X.side > 0])):
        for col in ("n48", "n24"):
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            line = (f"  {lab:18s} {col} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                    f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f})")
            if col == "n48":
                y = x[x.pl.notna()]
                dp, tp, npl = ct(y.n48 - y.pl, y.t)
                line += f" | парное плацебо (n={npl}) {y.pl.mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})"
            print(line)
    for lab, x0 in (("середина недели, все", M), ("середина недели, шорт", M[M.side < 0]), ("середина недели, лонг", M[M.side > 0])):
        x = x0[x0.n48.notna()]
        m, t, n = ct(x.n48, x.t)
        print(f"  {lab:24s} n48 n={n:4d} {m:+6.2%} (t {t:+4.1f})")


if __name__ == "__main__":
    main()
