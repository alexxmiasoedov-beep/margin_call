"""s133 — ⏰ по доле Upbit (гипотеза — ВЫВОДЫ.md, записана до расчёта). Доля Upbit за час — оборот Upbit / (Upbit + Bithumb +
фьючерс Binance) в долларах, считается функцией s15/kr_panel.coin только по Upbit в папке периода (там же s15/kr_panel.pkl
и s15/kr_candles_upbit.pkl). Шаг 1 — в каждой папке: MC_K=… python3 <repo>/research/s133/upbit_share.py share <период>
(сохраняет s133_up_<период>.pkl в /home/user/mc_data). Шаг 2 — из /home/user/mc_data: python3 … report."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

OUT = "/home/user/mc_data"
TRADES = {"2020–2022": ("s88/oos2020_trades.pkl", "2021-10-01"), "2022–2024": ("s88/oos_trades.pkl", "2023-10-01"),
          "2024–2026": ("s88/trades.pkl", "2025-12-01")}


def share(period):
    import kr_panel as KP  # noqa: E402  (K берётся из MC_K)
    C = {"upbit": KP.load("upbit")}
    u = C["upbit"]["USDT"]
    ser = pd.Series(u["c"].astype(float), index=u["t"])
    rate = {"upbit": lambda H: ser.reindex(np.union1d(ser.index, H)).ffill().bfill().reindex(H).values}
    KP.EXS = ("upbit",)
    P = pickle.load(open("s15/kr_panel.pkl", "rb"))
    rows = []
    for b in C["upbit"]:
        if b == "USDT":
            continue
        s = KP.fut_of(b)[0]
        if not s or s not in P:
            continue
        _, d = KP.coin(b, C, rate)
        d = d[d["T"] % 86400 == 3600][["T", "kr"]].rename(columns={"kr": "up"})
        full = P[s][["T", "kr", "bin"]]
        m = d.merge(full, on="T")
        m["share_up"] = m.up / (m.kr + m.bin).clip(lower=1.0)
        m["s"] = s
        rows.append(m[["s", "T", "share_up"]])
    X = pd.concat(rows, ignore_index=True)
    X.to_pickle(f"{OUT}/s133_up_{period}.pkl")
    print(period, "строк", len(X), "монет", X.s.nunique())


def report():
    from oi_test import ct  # noqa: E402
    allx = []
    for per, (f, cut) in TRADES.items():
        X = pd.read_pickle(f"{OUT}/{f}")
        X = X[X.open9 & (X.r1 >= 0.05) & (X.share >= 0.20) & X.S_10_25.notna()].copy()
        X["key"] = X.s.str.replace("USDT$", "", regex=True)
        U = pd.read_pickle(f"{OUT}/s133_up_{per}.pkl").rename(columns={"s": "key", "T": "t"})
        X = X.merge(U, on=["key", "t"], how="left")
        X["cut"] = pd.Timestamp(cut, tz="UTC").timestamp(); X["per"] = per
        print(f"\n{per}: событий ⏰ {len(X)}, доля Upbit известна у {X.share_up.notna().mean():.0%},"
              f" медиана {X.share_up.median():.0%}")
        for lab, y in (("U: доля Upbit ≥ 20%", X[X.share_up >= 0.20]), ("B: остальные", X[~(X.share_up >= 0.20)])):
            if len(y) < 8:
                print(f"  {lab:22s} n={len(y)}"); continue
            m, t, n = ct(y.S_10_25, y.t)
            print(f"  {lab:22s} n={n:4d} {m:+.2%} (t {t:+.1f}) в плюсе {(y.S_10_25 > 0).mean():.0%} | половины "
                  f"{y[y.t < y.cut].S_10_25.mean():+.2%} / {y[y.t >= y.cut].S_10_25.mean():+.2%} | сверх плацебо "
                  f"{(y.S_10_25 - y.pl_S_10_25).mean():+.2%}")
        allx.append(X)
    A = pd.concat(allx, ignore_index=True)
    print("\nшесть лет:")
    for lab, y in (("U: доля Upbit ≥ 20%", A[A.share_up >= 0.20]), ("B: остальные", A[~(A.share_up >= 0.20)])):
        m, t, n = ct(y.S_10_25, y.t)
        print(f"  {lab:22s} n={n:4d} {m:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    share(sys.argv[2]) if sys.argv[1] == "share" else report()
