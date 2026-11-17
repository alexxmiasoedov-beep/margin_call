"""s71 — против толпы счетов Binance (гипотеза — ВЫВОДЫ.md, записана до расчёта). Срез в 00:00 UTC по перпам
s22/top100.txt (торгуются ≥ 30 сут, есть отметка метрик за 00:00): отношение лонг/шорт всех счетов (s22/metrics_full,
колонка 5). Лонг трёх с наименьшим (основной) и шорт трёх с наибольшим; вход на закрытии свечи 00:00–00:15; выход 24 ч
или 3 сут, стоп 25%, без тейка; плацебо — та же монета за 45/90/135 сут. Запуск из папки с данными."""
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

EXITS = {"L_24h": dict(tp=None, sl=0.25, hold_h=24), "L_3d": dict(tp=None, sl=0.25, hold_h=72)}
N = 3


def load(sym):
    a = [np.load(f) for f in sorted(glob.glob(f"s22/metrics_full/{sym}/*.npy"))]
    a = [x for x in a if len(x)]
    if not a:
        return None
    a = np.concatenate(a)
    return a[np.argsort(a[:, 0])]


def entry(s, T):
    """Индекс 15-мин свечи 00:00–00:15 (вход на её закрытии)."""
    t = K[s]["t"]; i = int(np.searchsorted(t, T))
    return i if i < len(t) and t[i] == T else None


def main():
    top = open("s22/top100.txt").read().split()
    ratio, mom = {}, {}
    for s in top:
        if s not in K:
            continue
        m = load(s)
        if m is None:
            continue
        r = pd.Series(m[:, 5], index=m[:, 0].astype(np.int64))
        ratio[s] = r[(r.index % DAY == 0) & (r > 0)]
    R = pd.DataFrame(ratio).sort_index()
    rows = []
    for T, row in R.iterrows():
        T = int(T); ok = []
        for s, v in row.dropna().items():
            lo, hi = live(s)
            if T >= lo + 30 * DAY and T + 3 * DAY <= hi and entry(s, T) is not None:
                ok.append((v, s))
        if len(ok) < 30:
            continue
        ok.sort()
        allr = {}
        for v, s in ok:                                                   # средний доход лонга по срезу за сутки (для понимания)
            x = trade(s, entry(s, T), tp=None, sl=None, hold_h=24, side=1)
            if x:
                allr[s] = x["price"]
        avg = np.mean(list(allr.values())) if allr else np.nan
        a = K
        for grp, side, pick in (("лонг: толпа в шорте", 1, ok[:N]), ("шорт: толпа в лонге", -1, ok[-N:])):
            for v, s in pick:
                i = entry(s, T); c = a[s]["c"]; t = a[s]["t"]
                j = int(np.searchsorted(t, T - 14 * DAY))
                d = dict(g=grp, s=s, t=T, ratio=v, m14=float(c[i] / c[j] - 1) if j < i else np.nan,
                         rel=side * (allr.get(s, np.nan) - avg))
                for nm, kw in EXITS.items():
                    x = trade(s, i, side=side, **kw)
                    d[nm] = x["net"] if x else np.nan
                    p = [y["net"] for dd in (45, 90, 135) if (j2 := entry(s, T - dd * DAY)) is not None
                         and T - dd * DAY >= live(s)[0] and (y := trade(s, j2, side=side, **kw))]
                    d["pl_" + nm] = np.mean(p) if p else np.nan
                rows.append(d)
    X = pd.DataFrame(rows)
    os.makedirs("s71", exist_ok=True); X.to_pickle("s71/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Дней среза: {X.t.nunique()}, месяцев {months:.1f}")
    for g, x0 in X.groupby("g", sort=False):
        print(f"\n## {g}: медиана отношения {x0.ratio.median():.2f}, медиана дохода за 14 сут {x0.m14.median():+.1%},"
              f" сверх среза за сутки (без фандинга и комиссии) {x0.rel.mean():+.2%} (t {ct(x0.rel, x0.t)[1]:+.1f})")
        for col in EXITS:
            x = x0[x0[col].notna()]
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {col:6s} n={n:5d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
