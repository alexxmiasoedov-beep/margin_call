"""s104 — снятие хеджа после разлока (гипотеза — ВЫВОДЫ.md, записана до расчёта). События — s28/paths.pkl (разлоки ≥ 1%
монет в обращении), признак хеджа F7 — сумма начислений фандинга за [T − 7 сут, T). Лонг с T + 24 ч на 7 сут, стоп −25%,
без тейка (s15/common.trade, side=+1); ещё T → T + 7 сут и T + 1 → T + 4 сут. Плацебо — та же монета за 45/90/135 сут
без разлоков ≥ 1% в ±10 сут. Запуск из папки с данными: python3 <repo>/research/s104/hedge_test.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s103"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, funding, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402
from beta import index  # noqa: E402

EX = {"T+1→T+8": (1, 168), "T→T+7": (0, 168), "T+1→T+4": (1, 72)}


def deal(s, T, lag_d, hold_h):
    i = idx_at(s, T + lag_d * DAY)
    if i is None:
        return None
    r = trade(s, i, tp=None, sl=0.25, hold_h=hold_h, side=1)
    return r


def main():
    tI, I, _, _ = index()
    P = pd.read_pickle("s28/paths.pkl").sort_values("t")
    ev_t = {s: g.t.values for s, g in P.groupby("s")}
    rows, last_exit = [], {}
    for s, T, size, cliff, team in zip(P.s, P.t, P["size"], P.cliff, P.team):
        if s not in K:
            continue
        lo, hi = live(s)
        if T - 8 * DAY < lo or T + 9 * DAY > hi:
            continue
        if T + DAY < last_exit.get(s, -1):
            continue
        fr = funding(s)
        F7 = float(fr[(fr[:, 0] >= T - 7 * DAY) & (fr[:, 0] < T), 1].sum()) if len(fr) else np.nan
        d = dict(s=s, t=float(T), size=float(size), cliff=bool(cliff), team=float(team), F7=F7)
        for nm, (lag, h) in EX.items():
            r = deal(s, T, lag, h)
            d[nm] = r["net"] if r else np.nan
            if nm == "T+1→T+8" and r:
                last_exit[s] = T + DAY + r["bars"] * 900
                d["why"] = r["why"]
                i0 = np.searchsorted(tI + 900, T + DAY); i1 = min(i0 + r["bars"], len(I) - 1)
                d["mkt"] = I[i1] / I[min(i0, len(I) - 1)] - 1
            pl = []
            for dd in (45, 90, 135):
                Tp = T - dd * DAY
                if (np.abs(ev_t[s] - Tp) <= 10 * DAY).any():
                    continue
                y = deal(s, Tp, lag, h)
                if y:
                    pl.append(y["net"])
            d["pl_" + nm] = np.mean(pl) if pl else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s104/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"разлоков с торгуемым фьючерсом: {len(X)} ({len(X) / months:.1f} в мес.); F7: медиана {X.F7.median():+.2%}, "
          f"≤ −0,5% у {(X.F7 <= -0.005).mean():.0%}, ≤ −1% у {(X.F7 <= -0.01).mean():.0%}")
    groups = (("F7 ≤ −0,5% (основная)", X.F7 <= -0.005), ("F7 ≤ −1%", X.F7 <= -0.01), ("F7 ≤ −2%", X.F7 <= -0.02),
              ("F7 > −0,5% (хеджа нет)", X.F7 > -0.005), ("все разлоки", X.F7.notna()))
    for nm in EX:
        print(f"\n=== лонг {nm} ===")
        for lab, m in groups:
            x = X[m & X[nm].notna()]
            if len(x) < 8:
                continue
            mm, t, n = ct(x[nm], x.t); dp, tp, _ = ct(x[nm] - x["pl_" + nm], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            print(f"  {lab:24s} n={n:4d} ({n / months:4.1f}/мес) {mm:+6.2%} (t {t:+4.1f}) в плюсе {(x[nm] > 0).mean():3.0%} |"
                  f" половины {ct(h1[nm], h1.t)[0]:+6.2%} / {ct(h2[nm], h2.t)[0]:+6.2%} | плацебо {x['pl_' + nm].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")
    x = X[(X.F7 <= -0.005) & X["T+1→T+8"].notna()]
    h = x["T+1→T+8"] - x.mkt
    print(f"\nосновная с хеджем индексом альтов (лонг монеты − индекс): {h.mean():+.2%} (t {ct(h, x.t)[1]:+.1f}); "
          f"стопов {(x.why == 'стоп').mean():.0%}")
    for lab, m in (("cliff", x.cliff), ("linear", ~x.cliff), ("команда ≥ 50%", x.team >= 0.5), ("команда < 50%", x.team < 0.5),
                   ("≥ 5%", x["size"] >= 5), ("1–5%", x["size"] < 5)):
        y = x[m]
        if len(y) >= 8:
            print(f"  {lab:14s} n={len(y):4d} {y['T+1→T+8'].mean():+6.2%} (t {ct(y['T+1→T+8'], y.t)[1]:+4.1f})")


if __name__ == "__main__":
    main()
