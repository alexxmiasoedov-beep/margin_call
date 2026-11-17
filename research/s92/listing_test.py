"""s92 — листинг монеты к турецкой лире (BTCTurk — первая часовая свеча пары в s75/btcturk1h.pkl; Binance — первая
часовая свеча XXX/TRY, собрано в tr_listings.pkl) у монеты с фьючерсом Binance старше суток → шорт на закрытии первого
часа торгов: 7 сут со стопом 50% и 10 / 25 / 48 ч; плацебо — та же монета за 45/90/135 сут. Гипотеза — ВЫВОДЫ.md,
записана до расчёта. Запуск из папки с данными: python3 <путь>/s92/listing_test.py <tr_listings.pkl>"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

EXITS = {"S_7d": dict(tp=None, sl=0.50, hold_h=168), "S_10_25": dict(tp=0.10, sl=0.25, hold_h=48)}


def main():
    L = pickle.load(open(sys.argv[1], "rb"))
    ev = [("BTCTurk", s, t0) for c, s, t0 in L["bt"]] + [("Binance", s, t0) for b, s, t0, ok, same in L["bn"] if ok]
    rows = []
    for ex, s, t0 in ev:
        T = int(t0) + 3600
        i = idx_at(s, T)
        if i is None:
            continue
        r = dict(ex=ex, s=s, t=T)
        for nm, kw in EXITS.items():
            y = trade(s, i, **kw)
            r[nm] = y["net"] if y else np.nan
            p = [z["net"] for dd in (45, 90, 135) if (k := idx_at(s, T - dd * DAY)) is not None and (z := trade(s, k, **kw))]
            r["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(r)
    X = pd.DataFrame(rows)
    X.to_pickle("s92/trades.pkl")
    for lab, x0 in (("все", X), ("BTCTurk", X[X.ex == "BTCTurk"]), ("Binance", X[X.ex == "Binance"])):
        for col in EXITS:
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            print(f"  {lab:8s} {col:7s} n={n:3d} {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} | половины "
                  f"{ct(h1[col], h1.t)[0]:+6.2%} / {ct(h2[col], h2.t)[0]:+6.2%} | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
