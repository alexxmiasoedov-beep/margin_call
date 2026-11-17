"""s115 — доля Binance Alpha в пампе (гипотеза — ВЫВОДЫ.md, записана до расчёта). Пампы — s49/trades.pkl (+15% за ≤ 2 ч
из покоя). Доля Alpha — оборот Alpha к USDT за последний полный час до входа ÷ (Alpha + фьючерс за тот же час); тикер
сверяется по цене (Alpha × множитель к цене фьючерса — от 0,8 до 1,25). Шорт 10/25/48 и 7 сут / стоп 50%
(s15/common.trade), плацебо — та же монета за 45/90/135 сут. Запуск из папки с данными после alpha_fetch.py:
python3 <repo>/research/s115/alpha_test.py"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

EX = {"10/25/48": dict(tp=0.10, sl=0.25, hold_h=48), "7 сут": dict(tp=None, sl=0.50, hold_h=168)}


def mult(s):
    for p, m in (("1000000", 1e6), ("10000", 1e4), ("1000", 1e3)):
        if s.startswith(p):
            return m
    return 1.0


def main():
    A = {}
    for f in os.listdir("s115/alpha"):
        a = json.load(open(f"s115/alpha/{f}"))
        if a:
            A[f[:-5]] = {int(x[0]) // 1000: (float(x[4]), float(x[7])) for x in a}
    P = pd.read_pickle("s49/trades.pkl")
    P = P[P.s.isin(A)].copy()
    rows = []
    for s, T, kr, share in zip(P.s, P.t.astype(float), P.kr, P.share):
        H = int(T) // 3600 * 3600
        al = A[s].get(H - 3600)
        if al is None:
            continue
        a = K[s]; t = a["t"]
        j = np.searchsorted(t, H - 3600)
        if j + 4 > len(t) or t[j] != H - 3600:
            continue
        fut = float(a["qv"][j:j + 4].sum()); pc = float(a["c"][j + 3])
        ratio = al[0] * mult(s) / pc if pc > 0 else np.nan
        if not (0.8 <= ratio <= 1.25):
            continue
        sh = al[1] / (al[1] + fut) if al[1] + fut > 0 else 0.0
        i = idx_at(s, T)
        if i is None:
            continue
        d = dict(s=s, t=T, ash=sh, kr=kr, share=share)
        for nm, kw in EX.items():
            x = trade(s, i, side=-1, **kw)
            d[nm] = x["net"] if x else np.nan
            p = [y["net"] for dd in (45, 90, 135) if (jj := idx_at(s, T - dd * DAY)) is not None
                 and (y := trade(s, jj, side=-1, **kw))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s115/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"пампов токенов Alpha со сверенной ценой: {len(X)} ({len(X) / months:.1f} в мес.); доля Alpha: медиана {X.ash.median():.1%}, "
          f"≥ 20% у {(X.ash >= 0.2).mean():.0%}")
    other = ~((X.kr >= 0.2) | (X.share >= 0.259))
    for nm in EX:
        print(f"\n=== шорт {nm} ===")
        for lab, m in (("доля Alpha ≥ 20% (основная)", X.ash >= 0.2), ("  без 🇰🇷 и 🛒", (X.ash >= 0.2) & other),
                       ("доля Alpha ≥ 10%", X.ash >= 0.1), ("доля Alpha ≥ 30%", X.ash >= 0.3), ("доля Alpha < 5%", X.ash < 0.05)):
            x = X[m & X[nm].notna()]
            if len(x) < 8:
                print(f"  {lab:28s} n={len(x)}"); continue
            mm, t, n = ct(x[nm], x.t); dp, tp, _ = ct(x[nm] - x["pl_" + nm], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            print(f"  {lab:28s} n={n:4d} ({n / months:5.1f}/мес) {mm:+6.2%} (t {t:+4.1f}) в плюсе {(x[nm] > 0).mean():3.0%} |"
                  f" половины {ct(h1[nm], h1.t)[0]:+6.2%} ({len(h1)}) / {ct(h2[nm], h2.t)[0]:+6.2%} ({len(h2)}) |"
                  f" плацебо {x['pl_' + nm].mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
