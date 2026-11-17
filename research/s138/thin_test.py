"""s138 — тонкий стакан и откат пампа (гипотеза — ВЫВОДЫ.md, записана до загрузки стакана). Глубина — s138/depth.pkl
(depth.py). Пампы и доход шорта 10/25/48 — ~/mc_oos/s118_spot.pkl (с 01.01.2023) и s49/trades.pkl.
Шаг 1 — оборот фьючерса за 2 ч до t в папке периода (свечи периода из MC_K):
  2023–2024: cd ~/mc_oos && MC_K=… MC_F=… MC_CUT=2023-10-01 python3 <repo>/research/s138/thin_test.py flow 2023–2024
  2024–2026: cd /home/user/mc_data && python3 <repo>/research/s138/thin_test.py flow 2024–2026
Шаг 2 — сводка из /home/user/mc_data: python3 <repo>/research/s138/thin_test.py report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

OUT, DAY = "/home/user/mc_data", 86400
T0 = 1672531200 + 8 * 3600
PER = {"2023–2024": ("/home/user/mc_oos/s118_spot.pkl", "2023-01-01", "2024-10-01", "2023-10-01"),
       "2024–2026": (f"{OUT}/s49/trades.pkl", "2024-10-01", "2026-10-19", "2025-12-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def flow(per):
    from common import K  # noqa: E402
    f, t0, t1, _ = PER[per]
    X = pd.read_pickle(f)
    X = X[(X.t >= max(ts(t0), T0)) & (X.t < ts(t1))].copy()
    out = []
    for r in X.itertuples():
        a = K.get(r.s)
        if a is None:
            out.append(np.nan); continue
        j = int(np.searchsorted(a["t"], r.t - 900))            # свеча пампа: открытие t − 15 мин
        ok = j < len(a["t"]) and int(a["t"][j]) == r.t - 900 and j >= 7
        out.append(float(a["qv"][j - 7:j + 1].sum()) if ok else np.nan)
    X["flow"] = out
    X.to_pickle(f"{OUT}/s138_flow_{per}.pkl")
    print(per, "пампов", len(X), "оборот найден", int(np.isfinite(X.flow).sum()))


def diff(a, b, col="net"):
    da = a.groupby(pd.to_datetime(a.t, unit="s").dt.date)[col].mean()
    db = b.groupby(pd.to_datetime(b.t, unit="s").dt.date)[col].mean()
    d = a[col].mean() - b[col].mean(); se = np.sqrt(da.var() / len(da) + db.var() / len(db))
    return d, d / se if se > 0 else np.nan


def line(lab, x, months, cut):
    from oi_test import ct  # noqa: E402
    if len(x) < 8:
        return f"  {lab:30s} n={len(x)}"
    m, t, n = ct(x.net, x.t)
    dp = (x.net - x.pl).dropna()
    md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
    return (f"  {lab:30s} n={n:5d} ({n / months:5.1f}/мес) {m:+.2%} (t {t:+.1f}) в плюсе {(x.net > 0).mean():.0%} | "
            f"половины {x[x.t < cut].net.mean():+.2%} / {x[x.t >= cut].net.mean():+.2%} | сверх плацебо {md:+.2%} (t {td:+.1f})")


def report():
    from oi_test import ct  # noqa: E402
    D = pd.read_pickle(f"{OUT}/s138/depth.pkl")
    A = []
    for per, (_, t0, t1, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s138_flow_{per}.pkl").merge(D, on=["s", "t"], how="left")
        X["per"], X["cut"] = per, ts(cut)
        X["months"] = (ts(t1) - max(ts(t0), T0)) / (30.4 * DAY)
        A.append(X)
    A = pd.concat(A, ignore_index=True)
    A["L"] = (A.B2 + A.A2) / A.flow
    A["wd"] = A.A2late / A.A2                                   # уход продавцов: глубина продавцов в пампе к своей до пампа
    ok = np.isfinite(A.L) & (A.npre >= 100) & (A.flow > 0)
    print(f"пампов {len(A)}, с глубиной и оборотом {int(ok.sum())} ({ok.mean():.0%}); по периодам:",
          A[ok].groupby("per").size().to_dict())
    A = A[ok].copy()
    q1, q2 = A.L.quantile([1 / 3, 2 / 3]).values
    A["grp"] = np.where(A.L <= q1, "тонкий", np.where(A.L >= q2, "толстый", "средний"))
    print(f"пороги L (глубина ±2% / оборот 2 ч): тонкий ≤ {q1:.3f}, толстый ≥ {q2:.3f}")
    for per, X in A.groupby("per"):
        months, cut = X.months.iloc[0], X.cut.iloc[0]
        print(f"\n{per}:")
        for g in ("тонкий", "средний", "толстый"):
            print(line(g, X[X.grp == g], months, cut))
        d, t = diff(X[X.grp == "тонкий"], X[X.grp == "толстый"])
        rho = X[["L", "net"]].corr(method="spearman").iloc[0, 1]
        print(f"  тонкий − толстый: {d:+.2%} (t {t:+.1f}); ранговая связь L и дохода {rho:+.3f}")
        sp = X.share >= 0.259
        for lab, y in (("тонкий, 🛒-тип", X[(X.grp == "тонкий") & sp]), ("тонкий, не 🛒", X[(X.grp == "тонкий") & ~sp]),
                       ("толстый, 🛒-тип", X[(X.grp == "толстый") & sp]), ("толстый, не 🛒", X[(X.grp == "толстый") & ~sp])):
            print(line(lab, y, months, cut))
        w1, w2 = X.wd.quantile([1 / 3, 2 / 3]).values
        print(line(f"продавцы ушли (≤ {w1:.2f})", X[X.wd <= w1], months, cut))
        print(line(f"продавцы добавили (≥ {w2:.2f})", X[X.wd >= w2], months, cut))
    th = A[A.grp == "тонкий"]
    m, t, n = ct(th.net, th.t); dp = (th.net - th.pl).dropna(); md, td, _ = ct(dp, th.t[(th.net - th.pl).notna()])
    d, tdd = diff(th, A[A.grp == "толстый"])
    print(f"\nоба периода, тонкий стакан: n={n} {m:+.2%} (t {t:+.1f}), сверх плацебо {md:+.2%} (t {td:+.1f}); "
          f"тонкий − толстый {d:+.2%} (t {tdd:+.1f})")
    A.to_pickle(f"{OUT}/s138_all.pkl")


if __name__ == "__main__":
    flow(sys.argv[2]) if sys.argv[1] == "flow" else report()
