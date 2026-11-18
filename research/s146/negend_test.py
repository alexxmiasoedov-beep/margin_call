"""s146 — конец эпизода отрицательного фандинга (гипотеза — ВЫВОДЫ.md, записана до расчёта). Событие: ≥ 3 начисления подряд
≤ −0,3%, затем первое ≥ −0,01% в пределах 72 ч после последнего ≤ −0,3%; по монете не чаще раза в 48 ч. Шорт на закрытии
15-мин свечи, кончающейся в T + 15 мин: основная — 24 ч без тейка, стоп 25%; для отчёта 48 ч, 10/25/48, хедж индексом
альтов s103 на фактический срок, глубокие эпизоды (≤ −1%), плацебо 45/90/135 сут.
Запуск в папке периода: MC_K=… MC_F=… MC_CUT=… python3 <repo>/research/s146/negend_test.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, H1, OUT = 86400, 3600, "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}
SKIP = {"BTC", "ETH", "USDC", "FDUSD", "BUSD", "TUSD", "USDP", "DAI", "EUR", "BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD"}
NEG, NORM, RUN, GAP_H, COOL_H = -0.003, -0.0001, 3, 72, 48


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def events(fr, neg=NEG):
    """Начисления fr [время с, ставка] → [(T, глубина эпизода — минимальная ставка)]."""
    out, streak, armed, tneg, low, last = [], 0, False, None, 0.0, -10 ** 18
    for T, x in fr:
        T = int(T)
        if x <= neg:
            streak += 1; tneg = T; low = min(low, x)
            armed = armed or streak >= RUN
            continue
        streak = 0
        if armed and x >= NORM:
            if T - tneg <= GAP_H * H1 and T - last >= COOL_H * H1:
                out.append((T, low)); last = T
            armed, low = False, 0.0
        elif armed and T - tneg > GAP_H * H1:
            armed, low = False, 0.0
        elif not armed:
            low = 0.0
    return out


def run(per):
    from common import K, funding, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1, _ = PER[per]
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    def deal(s, te, **kw):
        i = idx_at(s, te)
        x = trade(s, i, side=-1, **kw) if i is not None else None
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
        if not len(fr):
            continue
        deep = {T for T, _ in events(fr, -0.01)}
        for T, low in events(fr):
            te = T + 900
            if not (ts(t0) <= te < ts(t1)) or te < lo + DAY:
                continue
            x, h = deal(s, te, tp=None, sl=0.25, hold_h=24)
            if not x:
                continue
            y, _ = deal(s, te, tp=None, sl=0.25, hold_h=48)
            z, _ = deal(s, te, tp=0.10, sl=0.25, hold_h=48)
            pl = [w["net"] for w in (deal(s, te - dd * DAY, tp=None, sl=0.25, hold_h=24)[0] for dd in (45, 90, 135)) if w]
            j = idx_at(s, te); a = K[s]
            pre = float(a["c"][j] / a["c"][j - 96] - 1) if j is not None and j >= 96 else np.nan
            rows.append(dict(s=s, t=te, low=low, deep=T in deep, net=x["net"], price=x["price"], fund=x["fund"], why=x["why"],
                             hed=h, n48=y["net"] if y else np.nan, n1025=z["net"] if z else np.nan,
                             pl=np.mean(pl) if pl else np.nan, pre=pre))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s146_{per}.pkl")
    print(per, "событий", len(X))


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (t0, t1, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s146_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(t1) - ts(t0)) / (30.4 * DAY); c = ts(cut)
        m, t, n = ct(X.net, X.t)
        mh, th, _ = ct(X.hed.dropna(), X.t[X.hed.notna()])
        m48, t48, _ = ct(X.n48.dropna(), X.t[X.n48.notna()]); m10, t10, _ = ct(X.n1025.dropna(), X.t[X.n1025.notna()])
        dp = (X.net - X.pl).dropna(); md, td, _ = ct(dp, X.t[(X.net - X.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
        d = X[X.deep]
        print(f"{per}: n={n} ({n / months:.1f}/мес) 24 ч {m:+.2%} (t {t:+.1f}) | половины {X[X.t < c].net.mean():+.2%} / "
              f"{X[X.t >= c].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | 48 ч {m48:+.2%} (t {t48:+.1f}) | "
              f"10/25/48 {m10:+.2%} (t {t10:+.1f})\n      сверх плацебо {md:+.2%} (t {td:+.1f}), плацебо {X.pl.mean():+.2%} | "
              f"цена {X.price.mean():+.2%}, фандинг {X.fund.mean():+.2%} | в плюсе {(X.net > 0).mean():.0%}, стопов "
              f"{(X.why == 'стоп').mean():.0%} | ход за 24 ч до T {X.pre.median():+.1%} (медиана) | глубокие n={len(d)} "
              f"{d.net.mean():+.2%}")
    A = pd.concat(A, ignore_index=True)
    m, t, n = ct(A.net, A.t); mh, th, _ = ct(A.hed.dropna(), A.t[A.hed.notna()])
    print(f"шесть лет: n={n} 24 ч {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
