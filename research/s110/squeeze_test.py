"""s110 — лонг пробоя недельного максимума при переполненных шортах (гипотеза — ВЫВОДЫ.md, записана до расчёта).
Событие на закрытии 15-мин свечи: цена выше максимума прошлых 7 сут, рост за 24 ч ≥ 5%, сумма фандинга за 24 ч ≤ −0,15%,
фьючерс старше 30 сут, оборот за 24 ч ≥ 5 млн $, одно событие на монету за 72 ч. Лонг: тейк 20 / стоп 10 / 48 ч
(ещё 24 ч со стопом 10; 7 сут со стопом 20). Сравнение — тот же пробой при фандинге ≥ 0. Плацебо — та же монета
за 45/90/135 сут. Запуск из папки с данными после s103/beta.py: python3 <repo>/research/s110/squeeze_test.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s105"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, funding, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402
from jumps_test import SKIP  # noqa: E402

EX = {"T20/S10/48ч": dict(tp=0.2, sl=0.1, hold_h=48), "S10/24ч": dict(tp=None, sl=0.1, hold_h=24),
      "S20/7сут": dict(tp=None, sl=0.2, hold_h=168)}


def events():
    out = []
    for s in K:
        if s in SKIP:
            continue
        a = K[s]; t = a["t"]; c = a["c"].astype(float); h = a["h"].astype(float); qv = a["qv"].astype(float)
        lo, hi = live(s)
        pm = pd.Series(h).rolling(672, min_periods=672).max().shift(1).values
        r24 = np.full(len(c), np.nan); r24[96:] = c[96:] / c[:-96] - 1
        v24 = pd.Series(qv).rolling(96).sum().values
        cand = np.flatnonzero((c > pm) & (r24 >= 0.05) & (v24 >= 5e6) & (t >= lo + 30 * DAY) & (t + 900 + 7 * DAY <= hi))
        if not len(cand):
            continue
        fr = funding(s)
        last = {"neg": -1e18, "pos": -1e18}
        for i in cand:
            T = float(t[i] + 900)
            f24 = float(fr[(fr[:, 0] > T - DAY) & (fr[:, 0] <= T), 1].sum()) if len(fr) else 0.0
            g = "neg" if f24 <= -0.0015 else ("pos" if f24 >= 0 else None)
            if g is None or T - last[g] < 3 * DAY:
                continue
            last[g] = T
            out.append((s, int(i), T, g, f24, float(r24[i])))
    return pd.DataFrame(out, columns=["s", "i", "t", "g", "f24", "r24"])


def main():
    E = events()
    J = pd.read_pickle("s103/beta_trades.pkl"); J = J[J.j.isin({"🇰🇷", "🛒"})]
    jt = {s: g.t.values for s, g in J.groupby("s")}
    rows = []
    for s, i, T, g, f24, r24 in E.itertuples(index=False):
        tt = jt.get(s, np.zeros(0))
        d = dict(s=s, t=T, g=g, f24=f24, r24=r24, ov=bool(((tt <= T) & (tt > T - DAY)).any()))
        for nm, kw in EX.items():
            x = trade(s, i, side=1, **kw)
            d[nm] = x["net"] if x else np.nan
            if nm == "T20/S10/48ч" and x:
                d["why"] = x["why"]; d["fund"] = x["fund"]
            p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, side=1, **kw))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s110/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    for nm in EX:
        print(f"\n=== лонг {nm} ===")
        for lab, x0 in (("фандинг ≤ −0,15% (основная)", X[X.g == "neg"]), ("  без 🇰🇷 🛒 за сутки", X[(X.g == "neg") & ~X.ov]),
                        ("фандинг ≥ 0 (сравнение)", X[X.g == "pos"])):
            x = x0[x0[nm].notna()]
            m, t, n = ct(x[nm], x.t); dp, tp, _ = ct(x[nm] - x["pl_" + nm], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            extra = f" тейков {(x.why == 'тейк').mean():.0%} стопов {(x.why == 'стоп').mean():.0%} фандинг {x.fund.mean():+.2%}" if nm == "T20/S10/48ч" else ""
            print(f"  {lab:28s} n={n:4d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[nm] > 0).mean():3.0%} |"
                  f" половины {ct(h1[nm], h1.t)[0]:+6.2%} / {ct(h2[nm], h2.t)[0]:+6.2%} | плацебо {x['pl_' + nm].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f}){extra}")


if __name__ == "__main__":
    main()
