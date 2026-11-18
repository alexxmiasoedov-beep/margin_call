"""s151 — откат после окна NAV ETF в 16:00 ET (гипотеза — ВЫВОДЫ.md, записана до расчёта). 15-мин свечи перпов Binance
(s2/k2y.pkl): ход монеты минус ход BTC за окно 15:00–16:00 ET (закрытия свечей, кончающихся в 15:00 и 16:00 ET) ≥ +0,5% →
шорт в 16:00 ET: основная — выход в 20:00 ET, стоп 5%; для отчёта — 17:00 ET и 09:30 ET следующего дня. Контроли: монеты ETF
до запуска, 25 ликвидных альтов без ETF, окно 11–12 ET. Запуск из /home/user/mc_data: python3 <repo>/research/s151/nav_test.py"""
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import ct, idx_at  # noqa: E402
from flow_test import alt_index  # noqa: E402

NY, DAY = ZoneInfo("America/New_York"), 86400
ETF = {"SOL": "2025-10-28", "LTC": "2025-10-28", "HBAR": "2025-10-28", "XRP": "2025-11-13", "DOGE": "2025-11-24",
       "LINK": "2025-12-02", "AVAX": "2026-01-26", "SUI": "2026-02-18", "DOT": "2026-03-06", "HYPE": "2026-05-12",
       "TRX": "2026-09-08", "NEAR": "2026-09-24"}
HOL = {"2024-11-28", "2024-12-25", "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26",
       "2025-06-19", "2025-07-04", "2025-09-01", "2025-11-27", "2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16",
       "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26"}
SKIP = {"BTC", "ETH", "USDC", "FDUSD", "BUSD", "TUSD", "USDP", "DAI", "EUR", "BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD"}
T0, T1, POST0, CUT = "2024-10-01", "2026-10-16", "2025-11-04", "2026-05-01"


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def et(day, hh, mm=0):
    return int(pd.Timestamp(f"{day} {hh:02d}:{mm:02d}", tz=NY).timestamp())


def close_at(s, t):
    i = idx_at(s, t)
    return (float(K[s]["c"][i]), i) if i is not None and int(K[s]["t"][i]) + 900 == t else (np.nan, None)


def main():
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    # контроль (b): 25 самых торгуемых альтов без ETF за 10.2024–09.2025 (по ликвидности, до расчёта доходов)
    a0, a1 = ts(T0), ts("2025-10-01")
    vol = {}
    for s, a in K.items():
        if s in SKIP or s in ETF:
            continue
        m = (a["t"] >= a0) & (a["t"] < a1)
        vol[s] = float(a["qv"][m].sum())
    CTRL = [s for s, _ in sorted(vol.items(), key=lambda x: -x[1])[:25]]
    print("контроль (b):", " ".join(CTRL))
    days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range(T0, T1)]
    days = [d for d in days if d not in HOL]
    rows = []
    for s in list(ETF) + CTRL:
        lo, hi = live(s)
        for d in days:
            for grp_h in ((15, 16), (11, 12)):
                if s in CTRL and grp_h[0] == 11:
                    continue
                ta, tb = et(d, grp_h[0]), et(d, grp_h[1])
                if ta - 900 < lo + DAY or tb + DAY > hi:
                    continue
                ca, _ = close_at(s, ta); cb, i = close_at(s, tb)
                ba, _ = close_at("BTC", ta); bb, _ = close_at("BTC", tb)
                if not all(np.isfinite([ca, cb, ba, bb])) or i is None:
                    continue
                rel = (cb / ca - 1) - (bb / ba - 1)
                if rel < 0.005:
                    continue
                on = s in ETF and tb >= ts(ETF[s]) + 7 * DAY
                grp = ("main" if on else "pre") if s in ETF and grp_h[0] == 15 else ("hour11" if s in ETF else "ctrl")
                if grp == "hour11" and not on:
                    continue
                if grp == "ctrl" and tb < ts(POST0):
                    grp = "ctrl_pre"
                x = trade(s, i, tp=None, sl=0.05, hold_h=4, side=-1)
                if not x:
                    continue
                y = trade(s, i, tp=None, sl=0.05, hold_h=1, side=-1)
                z = trade(s, i, tp=None, sl=0.05, hold_h=17.5, side=-1)
                t_end = int(K[s]["t"][i]) + 900 + int(x["bars"]) * 900
                pl = []
                for dd in (45, 90, 135):
                    j = idx_at(s, tb - dd * DAY)
                    w = trade(s, j, tp=None, sl=0.05, hold_h=4, side=-1) if j is not None else None
                    if w:
                        pl.append(w["net"])
                rows.append(dict(s=s, t=tb, grp=grp, rel=rel, net=x["net"], why=x["why"], hed=x["net"] + mv(tb, t_end),
                                 n1=y["net"] if y else np.nan, n17=z["net"] if z else np.nan, pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle("s151.pkl")
    months = (ts(T1) - ts(POST0)) / (30.4 * DAY); c = ts(CUT)
    for g in ("main", "pre", "ctrl", "ctrl_pre", "hour11"):
        x = X[X.grp == g]
        if len(x) < 8:
            print(g, len(x)); continue
        m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
        m1, t1, _ = ct(x.n1.dropna(), x.t[x.n1.notna()]); m17, t17, _ = ct(x.n17.dropna(), x.t[x.n17.notna()])
        dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()])
        print(f"{g:8s} n={n:5d} ({n / months:5.1f}/мес) 4 ч {m:+.3%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.3%} / "
              f"{x[x.t >= c].net.mean():+.3%} | с хеджем {mh:+.3%} | 1 ч {m1:+.3%} (t {t1:+.1f}) | 17,5 ч {m17:+.3%} (t {t17:+.1f}) | "
              f"сверх плацебо {md:+.3%} (t {td:+.1f}) | в плюсе {(x.net > 0).mean():.0%}")
    a = X[X.grp == "main"]
    for g in ("pre", "ctrl", "hour11"):
        b = X[X.grp == g]
        da = a.groupby(pd.to_datetime(a.t, unit="s").dt.date).net.mean(); db = b.groupby(pd.to_datetime(b.t, unit="s").dt.date).net.mean()
        d = a.net.mean() - b.net.mean(); se = np.sqrt(da.var() / len(da) + db.var() / len(db))
        print(f"основная − {g}: {d:+.3%} (t {d / se:+.1f})")


if __name__ == "__main__":
    main()
