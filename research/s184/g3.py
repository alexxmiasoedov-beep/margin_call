"""s184 Г3 — двойник ⏰ 🔝 👀 🇰🇷 по доле Кореи у монеты (гипотеза — ВЫВОДЫ.md, записана до расчёта).
kshare7 — оборот Upbit + Bithumb к воне за 7 полных суток UTC до суток входа / (Корея + перп + спот Binance), по дневной
панели s183 (daily_<период>.pkl), не меньше 5 суток с рынком к воне. Входы и доходы журналов — их собственные выходы
10 / 25 / 48 ч из файлов бэктестов (s88, s65, s83, s20, s118). Событие — kshare7 ≥ 20%, контроль — < 20%.
Запуск: python3 <repo>/research/s184/g3.py  → сводка в stdout, итог s184_g3.pkl в папке данных"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))
import common182 as C  # noqa: E402

DAY, OUT = C.DAY, C.OUT
O9 = lambda x: x.open9.astype(bool) & (x.r1 >= 0.05) & (x.share >= 0.20)  # noqa: E731
SRC = {
    "⏰": {"2020–2022": (f"{OUT}/s88/oos2020_trades.pkl", "t", "S_10_25", "pl_S_10_25", O9),
          "2022–2024": (f"{OUT}/s88/oos_trades.pkl", "t", "S_10_25", "pl_S_10_25", O9),
          "2024–2026": (f"{OUT}/s88/trades.pkl", "t", "S_10_25", "pl_S_10_25", O9)},
    "🔝": {"2022–2024": ("/home/user/mc_oos/s65/trades.pkl", "t", "S_10_25", "pl_S_10_25", None),
          "2024–2026": (f"{OUT}/s65/trades.pkl", "t", "S_10_25", "pl_S_10_25", None)},
    "👀": {"2024–2026": (f"{OUT}/s83/trades.pkl", "t", "S_10_25", "pl_S_10_25", None)},
    "🇰🇷": {"2020–2022": ("/home/user/mc_2020/s118_kr.pkl", "t", "net", "pl", None),
           "2022–2024": ("/home/user/mc_oos/s118_kr.pkl", "t", "net", "pl", None),
           "2024–2026": (f"{OUT}/s20/trades.pkl", "te", "net", None, lambda x: x.journal == "🇰🇷")},
}


def kshare(per):
    P = pd.read_pickle(f"{OUT}/s183/daily_{per}.pkl")[["d", "s", "qv", "sqv", "krv"]]
    return {s: (y.d.to_numpy(np.int64), y.qv.fillna(0).to_numpy(), y.sqv.fillna(0).to_numpy(), y.krv.to_numpy())
            for s, y in P.sort_values("d").groupby("s")}


def ks_at(D, s, t):
    v = D.get(s)
    if v is None:
        return np.nan
    d, qv, sqv, krv = v
    d0 = (int(t) // DAY) * DAY
    m = (d >= d0 - 7 * DAY) & (d < d0)
    k = krv[m]
    if np.isfinite(k).sum() < 5:
        return np.nan
    kv = np.nansum(k)
    den = kv + qv[m].sum() + sqv[m].sum()
    return kv / den if den > 0 else np.nan


def build():
    rows = []
    for per in C.PER:
        D = kshare(per)
        t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
        for j, src in SRC.items():
            if per not in src:
                continue
            f, tc, nc, pc, cond = src[per]
            X = pd.read_pickle(f)
            if cond is not None:
                X = X[cond(X)]
            X = X.rename(columns={tc: "t"})
            X = X[(X.t >= t0) & (X.t < t1) & X[nc].notna()]
            for r in X.itertuples():
                s = r.s[:-4] if isinstance(r.s, str) and r.s.endswith("USDT") else r.s
                rows.append(dict(j=j, per=per, s=s, t=int(r.t), net=float(getattr(r, nc)),
                                 pl=float(getattr(r, pc)) if pc else np.nan, ks=ks_at(D, s, r.t)))
    R = pd.DataFrame(rows)
    R.to_pickle(f"{OUT}/s184_g3.pkl")
    return R


def report(R):
    print("Г3 — двойник ⏰ 🔝 👀 🇰🇷: вход при доле Кореи у монеты за 7 сут ≥ 20% против < 20% (выходы журналов 10/25/48 ч)\n")
    for j in SRC:
        parts = []
        print(f"{j}:")
        for per in C.PER:
            x = R[(R.j == j) & (R.per == per)]
            if not len(x):
                continue
            hi, lo = x[x.ks >= 0.2], x[x.ks < 0.2]
            z = x[x.ks.notna()]
            d, se = C.diff(z.net, z.ks >= 0.2, z.t)
            parts.append((d, se, len(hi)))
            print(f"  {per}: ≥ 20% {C.line(hi, per)}")
            print(f"  {' ' * len(per)}  < 20% {C.line(lo, per)}")
            print(f"  {' ' * len(per)}  нет рынка к воне или данных: n={int(x.ks.isna().sum())} {x[x.ks.isna()].net.mean():+.2%}")
            print(f"  {' ' * len(per)}  Δ = {d:+.2%} (t {d / se:+.1f}) | доза < 10 / 10–20 / 20–35 / ≥ 35%: " +
                  " / ".join(f"{x[(x.ks >= a) & (x.ks < b)].net.mean():+.2%} ({int(((x.ks >= a) & (x.ks < b)).sum())})"
                             for a, b in ((0, 0.1), (0.1, 0.2), (0.2, 0.35), (0.35, 9))))
        m, t = C.combine(parts)
        print(f"  вместе: Δ = {m:+.2%} (t {t:+.1f})\n")


if __name__ == "__main__":
    report(pd.read_pickle(f"{OUT}/s184_g3.pkl") if len(sys.argv) > 1 and sys.argv[1] == "report" else build())
