"""s56 — тихое накопление на споте (гипотеза — ВЫВОДЫ.md, записана до расчёта). Час h монеты со спотом Binance: оборот спота
≥ 5× медианы часового оборота за прошлые 168 ч, доля покупок рыночными ≥ 60% (зеркало ≤ 40%), фьючерс за час −1…+2%, за
24 ч до конца часа |изменение| < 10%; не чаще раза в 48 ч на монету. Вход на закрытии первой 15-мин свечи после конца часа.
Лонг 10/10/48 и лонг 7 сут со стопом 20%; зеркало — шорт 10/10/48. Плацебо — та же монета за 45/90/135 сут.
Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

EXITS = {"L_10_10": dict(tp=0.10, sl=0.10, hold_h=48, side=1), "L_7d": dict(tp=None, sl=0.20, hold_h=168, side=1),
         "S_10_10": dict(tp=0.10, sl=0.10, hold_h=48, side=-1)}


def events():
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    out = []
    for s, sp in SP.items():
        if s not in K:
            continue
        a = K[s]; t = a["t"].astype(np.int64); c = a["c"].astype(float)
        tt = sp[:, 0].astype(np.int64); v = sp[:, 1].astype(float); tb = sp[:, 2].astype(float)
        med = pd.Series(v).shift(1).rolling(168, min_periods=120).median().values
        last = -1e18
        for i in np.flatnonzero((v >= 5 * med) & (v > 0)):
            He = int(tt[i]) + 3600                                      # конец часа h
            j = int(np.searchsorted(t, He - 900))                       # свеча фьючерса, закрывающаяся в конце часа
            if j < 96 or j + 1 >= len(t) or t[j] != He - 900 or a["qv"][j] <= 0:
                continue
            r1 = c[j] / c[j - 4] - 1; r24 = c[j] / c[j - 96] - 1
            if not (-0.01 <= r1 <= 0.02) or abs(r24) >= 0.10:
                continue
            buy = tb[i] / v[i]
            side = 1 if buy >= 0.60 else (-1 if buy <= 0.40 else 0)
            if side == 0 or He - last < 48 * 3600:
                continue
            last = He
            out.append(dict(s=s, t=He, j=j + 1, buy=buy, side=side, x=v[i] / med[i]))
    return pd.DataFrame(out)


def main():
    E = events()
    rows = []
    for e in E.itertuples():
        d = dict(s=e.s, t=e.t, side=e.side, buy=e.buy, x=e.x)
        for nm, kw in EXITS.items():
            if (kw["side"] == 1) != (e.side == 1):
                continue
            r = trade(e.s, e.j, **kw)
            d[nm] = r["net"] if r else np.nan
            p = [y["net"] for dd in (45, 90, 135) if e.j - dd * 96 >= 96 and (y := trade(e.s, e.j - dd * 96, **kw))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s56/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий: {len(X)} за {months:.1f} мес.; покупки ≥ 60%: {(X.side == 1).sum()}, продажи ≤ 40%: {(X.side == -1).sum()}")

    def line(lab, x, col):
        x = x[x[col].notna()]
        if len(x) < 8:
            return f"  {lab:34s} {col:8s} мало ({len(x)})"
        m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
        a, b = x[x.t < CUT][col].mean(), x[x.t >= CUT][col].mean()
        return (f"  {lab:34s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x['pl_' + col].mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    L, S = X[X.side == 1], X[X.side == -1]
    print(line("ОСНОВНАЯ: покупки ≥ 60% → лонг", L, "L_10_10"))
    print(line("  то же, 7 сут", L, "L_7d"))
    print(line("зеркало: продажи → шорт", S, "S_10_10"))


if __name__ == "__main__":
    main()
