"""s58 — памп без спота нигде → лонг (гипотеза — ВЫВОДЫ.md, записана до расчёта). Пампы — s54/trades.pkl (суммарная доля
спота Binance + Корея + Coinbase за последний полный час до закрытия свечи пампа). Отбор — суммарная доля < 5%. Лонг
с закрытия свечи пампа: 10/10/48 (основной) и 30/15/48; одна сделка на монету за 48 ч; плацебо — та же монета за
45/90/135 сут. Запуск из папки с данными (после s54)."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

EXITS = {"L_10_10": dict(tp=0.10, sl=0.10, hold_h=48, side=1), "L_30_15": dict(tp=0.30, sl=0.15, hold_h=48, side=1)}


def main():
    X = pd.read_pickle("s54/trades.pkl")
    X = X[X.all_share < 0.05].copy()
    rows = []
    for r in X.itertuples():
        j = int(np.searchsorted(K[r.s]["t"], r.t - 900))
        d = dict(s=r.s, t=r.t)
        for nm, kw in EXITS.items():
            x = trade(r.s, j, **kw)
            d[nm] = x["net"] if x else np.nan
            p = [y["net"] for dd in (45, 90, 135) if j - dd * 96 >= 96 and (y := trade(r.s, j - dd * 96, **kw))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    Y = pd.DataFrame(rows)
    Y.to_pickle("s58/trades.pkl")
    months = (Y.t.max() - Y.t.min()) / (30.4 * DAY)
    print(f"Пампов без спота нигде: {len(Y)} ({len(Y) / months:.0f} в месяц)")
    for col in EXITS:
        x = Y[Y[col].notna()]
        m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
        a, b = x[x.t < CUT][col].mean(), x[x.t >= CUT][col].mean()
        print(f"  {col:8s} n={n:4d} {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} | половины {a:+6.2%} / {b:+6.2%}"
              f" | плацебо {x['pl_' + col].mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
