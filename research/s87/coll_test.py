"""s87 — снижение залогового коэффициента монеты на Binance → шорт (гипотеза — ВЫВОДЫ.md, записана до расчёта доходов).
События s87/coll.pkl; фьючерс ≥ 30 сут; одно событие на монету за 7 сут. Шорт на закрытии первого часа после публикации,
выход через 24 ч после вступления в силу (основной), в момент вступления, 10/25/48; стоп 50%; зеркало — повышение → лонг.
Плацебо — та же монета за 45/90/135 сут, та же длительность. Запуск из папки с данными."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s66"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, live  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from attn_test import idx_at, trade  # noqa: E402


def main():
    X = pd.read_pickle("s87/coll.pkl").sort_values("ann")
    rows, last = [], {}
    for r in X.itertuples():
        side = -1 if r.after < r.before else (1 if r.after > r.before else 0)
        if not side:
            continue
        s, _ = fut_of(r.coin)
        if not s or s not in K:
            continue
        T = int(np.ceil(r.ann / 3600) * 3600)
        lo, hi = live(s)
        if T < lo + 30 * DAY or r.eff + 8 * DAY > hi or T - last.get((s, side), -1e18) < 7 * DAY:
            continue
        i = idx_at(s, T)
        if i is None:
            continue
        last[(s, side)] = T
        h_main = max(1.0, round((r.eff + DAY - T) / 900) / 4); h_eff = max(1.0, round((r.eff - T) / 900) / 4)
        d = dict(s=s, t=T, side=side, drop=r.before - r.after, zero=r.after == 0, hold=h_main)
        for nm, kw in (("main", dict(tp=None, sl=0.50, hold_h=h_main)), ("eff", dict(tp=None, sl=0.50, hold_h=h_eff)),
                       ("S_10_25", dict(tp=0.10, sl=0.25, hold_h=48))):
            x = trade(s, i, side=side, **kw)
            d[nm] = x["net"] if x else np.nan
            p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and T - dd * DAY >= lo
                 and (y := trade(s, j, side=side, **kw))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    E = pd.DataFrame(rows)
    E.to_pickle("s87/trades.pkl")
    months = (E.t.max() - E.t.min()) / (30.4 * DAY)
    D = E[E.side < 0]
    print(f"Снижений с фьючерсом: {len(D)} ({len(D) / months:.1f} в месяц), повышений: {(E.side > 0).sum()};"
          f" медианный срок сделки {D.hold.median():.0f} ч; обнулений {D.zero.sum()}")
    for lab, x0 in (("снижение → шорт (основная)", D), ("снижение ≥ 20 п. п.", D[D["drop"] >= 20]), ("обнуление", D[D.zero]),
                    ("повышение → лонг", E[E.side > 0])):
        for col, nm in (("main", "до +24 ч"), ("eff", "до вступления"), ("S_10_25", "10/25/48")):
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:28s} {nm:14s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
