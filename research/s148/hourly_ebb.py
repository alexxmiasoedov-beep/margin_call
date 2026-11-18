"""s148 — часовой отлив (гипотеза — ВЫВОДЫ.md, записана до расчёта). Событие — начисление Binance с часовым интервалом
(прошлое ≤ 61 мин назад, следующее через 59–61 мин), ставка ≤ −0,1% (основная группа ≤ −0,3%). Шорт T + 15 мин → T + 45 мин,
стоп 15%; проверка механизма — шорт T − 45 мин → T − 15 мин того же события; хедж — индекс альтов s103; плацебо — та же монета
за 45/90/135 сут. Запуск из /home/user/mc_data: python3 <repo>/research/s148/hourly_ebb.py run | report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, OUT = 86400, "/home/user/mc_data"
CUT = int(pd.Timestamp("2026-01-01", tz="UTC").timestamp())
SKIP = {"BTC", "ETH", "USDC", "FDUSD", "BUSD", "TUSD", "USDP", "DAI", "EUR", "BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD"}


def run():
    from common import K, funding, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    def deal(s, te):
        i = idx_at(s, te)
        x = trade(s, i, tp=None, sl=0.15, hold_h=0.5, side=-1) if i is not None else None
        if not x:
            return None, np.nan
        t_end = int(K[s]["t"][i]) + 900 + int(x["bars"]) * 900
        return x, x["net"] + mv(te, t_end)

    rows = []
    for s in K:
        if s in SKIP:
            continue
        lo, hi = live(s)
        if not np.isfinite(lo):
            continue
        fr = funding(s)
        if len(fr) < 3:
            continue
        t, r = fr[:, 0].astype(np.int64), fr[:, 1]
        for i in np.flatnonzero(r <= -0.001):
            if i == 0 or i + 1 >= len(t):
                continue
            if not (t[i] - t[i - 1] <= 3660 and 3540 <= t[i + 1] - t[i] <= 3660):
                continue
            T = int(t[i])
            if T - 45 * 60 < lo + DAY:
                continue
            x, h = deal(s, T + 900)
            if not x:
                continue
            y, _ = deal(s, T - 2700)
            pl = [z["net"] for z in (deal(s, T + 900 - dd * DAY)[0] for dd in (45, 90, 135)) if z]
            rows.append(dict(s=s, t=T + 900, r=float(r[i]), net=x["net"], price=x["price"], fund=x["fund"], why=x["why"],
                             hed=h, pre=y["net"] if y else np.nan, pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s148.pkl")
    print("событий", len(X), "≤ −0,3%:", int((X.r <= -0.003).sum()))


def report():
    from oi_test import ct  # noqa: E402
    X = pd.read_pickle(f"{OUT}/s148.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    for name, x in (("≤ −0,3% (основная)", X[X.r <= -0.003]), ("≤ −0,1%", X), ("≤ −1%", X[X.r <= -0.01]),
                    ("−0,3…−1%", X[(X.r <= -0.003) & (X.r > -0.01)])):
        m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
        dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()])
        dd = (x.net - x.pre).dropna(); mpp, tpp, _ = ct(dd, x.t[(x.net - x.pre).notna()])
        print(f"{name}: n={n} ({n / months:.0f}/мес, монет {x.s.nunique()}) T+15→T+45 {m:+.3%} (t {t:+.1f}) | половины "
              f"{x[x.t < CUT].net.mean():+.3%} / {x[x.t >= CUT].net.mean():+.3%} | с хеджем {mh:+.3%} (t {th:+.1f}) | "
              f"сверх плацебо {md:+.3%} (t {td:+.1f}) | до T (T−45→T−15) {x.pre.mean():+.3%}, после − до {mpp:+.3%} "
              f"(t {tpp:+.1f}) | цена {x.price.mean():+.3%}, в плюсе {(x.net > 0).mean():.0%}")


if __name__ == "__main__":
    run() if sys.argv[1] == "run" else report()
