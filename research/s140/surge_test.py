"""s140 — 🛒 с всплеском оборота (гипотеза — ВЫВОДЫ.md, записана до расчёта). V = оборот фьючерса за 8 свечей до закрытия
свечи пампа t / средний оборот 8 свечей за [t − 7 сут − 2 ч, t − 2 ч). Порог — медиана V 🛒-пампов 2024–2026 гг.
Шаг 1 — V в папке периода (свечи из MC_K): python3 <repo>/research/s140/surge_test.py v <период>;
шаг 2 — сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

OUT, DAY = "/home/user/mc_data", 86400
PER = {"2020–2022": ("/home/user/mc_2020/s118_spot2020.pkl", "2020-10-01", "2022-10-01", "2021-10-01"),
       "2022–2024": ("/home/user/mc_oos/s118_spot.pkl", "2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": (f"{OUT}/s49/trades.pkl", "2024-10-01", "2026-10-19", "2025-12-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def vcol(per):
    from common import K  # noqa: E402
    f, t0, t1, _ = PER[per]
    X = pd.read_pickle(f)
    X = X[(X.t >= ts(t0)) & (X.t < ts(t1)) & (X.share >= 0.259)].copy()
    out = []
    for r in X.itertuples():
        a = K.get(r.s)
        j = int(np.searchsorted(a["t"], r.t - 900)) if a is not None else -1
        if a is None or j >= len(a["t"]) or int(a["t"][j]) != r.t - 900 or j < 8 + 7 * 96:
            out.append(np.nan); continue
        q = a["qv"].astype(float)
        flow = q[j - 7:j + 1].sum()
        base = q[j - 8 - 7 * 96 + 1:j - 7].mean() * 8            # средний оборот 2 ч за 7 сут до начала окна пампа
        out.append(flow / base if base > 0 else np.nan)
    X["V"] = out
    X.to_pickle(f"{OUT}/s140_{per}.pkl")
    print(per, "🛒-пампов", len(X), "с V", int(np.isfinite(X.V).sum()))


def diff(a, b):
    da = a.groupby(pd.to_datetime(a.t, unit="s").dt.date).net.mean()
    db = b.groupby(pd.to_datetime(b.t, unit="s").dt.date).net.mean()
    d = a.net.mean() - b.net.mean(); se = np.sqrt(da.var() / len(da) + db.var() / len(db))
    return d, d / se if se > 0 else np.nan


def report():
    from oi_test import ct  # noqa: E402
    D = {p: pd.read_pickle(f"{OUT}/s140_{p}.pkl") for p in PER}
    thr = D["2024–2026"].V.median()
    print(f"порог V (медиана 🛒 2024–2026): {thr:.2f}")
    for per, X in D.items():
        X = X[np.isfinite(X.V)]
        cut = ts(PER[per][3]); months = (ts(PER[per][2]) - ts(PER[per][1])) / (30.4 * DAY)
        print(f"\n{per}: медиана V {X.V.median():.2f}")
        for lab, y in (("высокий V", X[X.V >= thr]), ("низкий V", X[X.V < thr])):
            m, t, n = ct(y.net, y.t); dp = (y.net - y.pl).dropna()
            md, td, _ = ct(dp, y.t[(y.net - y.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
            print(f"  {lab:10s} n={n:4d} ({n / months:4.1f}/мес) {m:+.2%} (t {t:+.1f}) в плюсе {(y.net > 0).mean():.0%} | половины "
                  f"{y[y.t < cut].net.mean():+.2%} / {y[y.t >= cut].net.mean():+.2%} | сверх плацебо {md:+.2%} (t {td:+.1f})")
        d, t = diff(X[X.V >= thr], X[X.V < thr])
        print(f"  высокий − низкий: {d:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    vcol(sys.argv[2]) if sys.argv[1] == "v" else report()
