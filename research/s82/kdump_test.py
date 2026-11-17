"""s82 — обвал (зеркало пампа 🇰🇷: −15% от спокойной базы за ≤ 2 ч, не чаще раза в сутки) с долей Кореи в обороте
последнего полного часа ≥ 10% (основная) → лонг на закрытии свечи обвала, тейк 10 / стоп 25 / 48 ч (основной) или 24 ч
со стопом 15%; плацебо — та же монета за 45/90/135 сут (гипотеза — ВЫВОДЫ.md, записана до расчёта). Запуск из папки
с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

EX = {"L_10_25": dict(tp=0.10, sl=0.25, hold_h=48), "L_24h": dict(tp=None, sl=0.15, hold_h=24)}


def dumps(a):
    c, l = a["c"].astype(float), a["l"].astype(float)
    n = len(c); calm = np.zeros(n, bool); calm[8:] = np.abs(c[8:] / c[:-8] - 1) <= 0.05
    hit = np.zeros(n, bool); ls = pd.Series(l)
    for L in range(1, 9):
        mn = ls.rolling(L, min_periods=L).min().values
        base = np.r_[np.full(L, np.nan), c[:-L]]; cb = np.r_[np.zeros(L, bool), calm[:-L]]
        hit |= cb & (mn <= base * 0.85) & (np.arange(n) - L >= 8)
    nz = np.flatnonzero(a["qv"] > 0)
    if not len(nz):
        return np.array([], int)
    hit &= (np.arange(n) >= nz[0] + 96) & (np.arange(n) <= nz[-1]) & (a["qv"] > 0)
    out, last = [], -10 ** 9
    for j in np.flatnonzero(hit):
        if j - last >= 96:
            out.append(int(j)); last = j
    return np.array(out, int)


def main():
    KP = pickle.load(open("s15/kr_panel.pkl", "rb"))
    rows = []
    for s, d in KP.items():
        a = K[s]; js = dumps(a)
        sh = d.set_index("T").share
        for j in js:
            T = int(a["t"][j]) + 900; H = (T // 3600) * 3600
            share = sh.get(H, np.nan)
            if not share >= 0.10:
                continue
            r = dict(s=s, t=T, share=share)
            for nm, kw in EX.items():
                x = trade(s, j, side=1, **kw)
                r[nm] = x["net"] if x else np.nan
                p = [y["net"] for dd in (45, 90, 135) if (k := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, k, side=1, **kw))]
                r["pl_" + nm] = np.mean(p) if p else np.nan
            rows.append(r)
    X = pd.DataFrame(rows)
    X.to_pickle("s82/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Обвалов с долей Кореи ≥ 10%: {len(X)} ({len(X) / months:.1f} в месяц)")
    for lab, x0 in (("доля ≥ 10% (основная)", X), ("доля ≥ 20%", X[X.share >= 0.20]), ("доля 10–20%", X[X.share < 0.20])):
        for col in EX:
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:22s} {col:7s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
