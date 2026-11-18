"""s144 — дневная свеча с отказом (гипотеза — ВЫВОДЫ.md, записана до расчёта). Дневные свечи UTC — из 15-мин свечей периода
(MC_K). Событие: максимум суток ≥ +15% и закрытие ≤ +5% к закрытию прошлых суток, оборот суток ≥ 2× среднего за 7 сут.
Шорт на закрытии суток: основная — 10/25/48; для отчёта — 24 ч без тейка, стоп 25%; контроль — максимум ≥ +15% и закрытие
≥ +12%. Хедж — индекс альтов s103 на фактический срок; плацебо — та же монета за 45/90/135 сут.
Запуск в папке периода: MC_K=… MC_F=… MC_CUT=… python3 <repo>/research/s144/wick_test.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, OUT = 86400, "/home/user/mc_data"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}
SKIP = {"BTC", "ETH", "USDC", "FDUSD", "BUSD", "TUSD", "USDP", "DAI", "BTCDOM", "DEFI", "FOOTBALL", "BLUEBIRD"}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def daily(a):
    """Дневные свечи UTC из 15-мин: время начала суток, макс, закрытие, оборот; сутки только полные (96 свечей)."""
    t = a["t"].astype(np.int64)
    off = int(((-t[0]) % DAY) // 900)
    n = (len(t) - off) // 96
    sl = slice(off, off + 96 * n)
    r = lambda k: a[k][sl].astype(float).reshape(n, 96)
    return t[sl].reshape(n, 96)[:, 0], r("h").max(1), r("c")[:, -1], r("qv").sum(1), r("qv").min(1)


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1, _ = PER[per]
    T, I = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T, a - 900, "right")) - 1; j = int(np.searchsorted(T, b - 900, "right")) - 1
        return I[j] / I[i] - 1 if 0 <= i <= j < len(I) else np.nan

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
        d0, H, C, Q, qmin = daily(K[s])
        for k in range(8, len(d0)):
            te = int(d0[k]) + DAY                                    # закрытие суток k
            if not (ts(t0) <= te < ts(t1)) or d0[k] < lo + 30 * DAY or te + 2 * DAY > hi or qmin[k] <= 0:
                continue
            prev = C[k - 1]
            if prev <= 0 or H[k] < prev * 1.15:
                continue
            avg7 = Q[k - 7:k].mean()
            if not avg7 > 0 or Q[k] < 2 * avg7:
                continue
            c = C[k] / prev - 1
            grp = "отказ" if c <= 0.05 else ("без отказа" if c >= 0.12 else None)
            if grp is None:
                continue
            x, h = deal(s, te, tp=0.10, sl=0.25, hold_h=48)
            if not x:
                continue
            y, _ = deal(s, te, tp=None, sl=0.25, hold_h=24)
            pl = [z["net"] for z in (deal(s, te - dd * DAY, tp=0.10, sl=0.25, hold_h=48)[0] for dd in (45, 90, 135)) if z]
            rows.append(dict(s=s, t=te, grp=grp, hi=H[k] / prev - 1, c=c, net=x["net"], why=x["why"], hed=h,
                             n24=y["net"] if y else np.nan, pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s144_{per}.pkl")
    print(per, "событий", X.groupby("grp").size().to_dict() if len(X) else 0)


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (t0, t1, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s144_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(t1) - ts(t0)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}:")
        for g in ("отказ", "без отказа"):
            x = X[X.grp == g]
            if len(x) < 8:
                print(f"  {g:10s} n={len(x)}"); continue
            m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()]); m24, t24, _ = ct(x.n24.dropna(), x.t[x.n24.notna()])
            dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
            print(f"  {g:10s} n={n:4d} ({n / months:5.1f}/мес) 10/25/48 {m:+.2%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.2%} / "
                  f"{x[x.t >= c].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | 24 ч {m24:+.2%} (t {t24:+.1f}) | "
                  f"сверх плацебо {md:+.2%} (t {td:+.1f})")
    A = pd.concat(A, ignore_index=True)
    print("\nшесть лет:")
    for g in ("отказ", "без отказа"):
        x = A[A.grp == g]; m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
        print(f"  {g}: n={n} 10/25/48 {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
