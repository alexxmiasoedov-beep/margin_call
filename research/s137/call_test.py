"""s137 — призывы каналов сигналов (гипотеза — ВЫВОДЫ.md, записана до расчёта). События — s137/calls.pkl (calls.py).
H1: призыв купить → шорт на закрытии первой 15-мин свечи, закрывшейся не раньше чем через 5 мин после поста, 7 сут,
стоп +50%, без тейка (s15/common.trade); для отчёта — 10/25/48. H2: призыв в шорт → лонг 7 сут, стоп 50%. H3: отчёт
о цели по монете без призыва этих каналов за 7 сут → шорт 7 сут, стоп 50%. Одна сделка на монету за 7 сут в каждой
гипотезе. Плацебо — та же монета за 45/90/135 сут. Запуск в папке периода: MC_K=… MC_F=… MC_CUT=… python3
<repo>/research/s137/call_test.py <период>; сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))

DAY, LAG = 86400, 300
OUT = "/home/user/mc_data"
CALLS = f"{OUT}/s137/calls.pkl"
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-19", "2025-12-01")}
SKIP = {"BTC", "ETH", "USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USDP", "USDE", "USD1", "WBTC", "BTCDOM", "DEFI"}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def run(per):
    from common import K, fut_of, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    t0, t1, _ = PER[per]
    C = pd.read_pickle(CALLS)
    C = C[(C.t >= ts(t0)) & (C.t < ts(t1)) & ~C.coin.isin(SKIP)].sort_values("t")
    rows, last, called = [], {}, {}
    for r in C.itertuples():
        key, mult = fut_of(r.coin)
        if key is None:
            continue
        lo, hi = live(key)
        if lo + DAY > r.t or r.t + 8 * DAY > hi:
            continue
        ip = idx_at(key, r.t)                                   # последняя свеча, закрытая до поста
        ie = idx_at(key, r.t + LAG + 899)                       # первая свеча, закрытая ≥ 5 мин после поста
        if ip is None or ie is None or ip < 96:
            continue
        c = K[key]["c"].astype(float)
        if pd.notna(r.px) and r.px > 0 and not 0.7 <= c[ip] / (r.px * mult) <= 1.43:   # цена в посте — не та монета
            continue
        if r.typ == "призыв":
            called[key] = r.t
        hyp = ("H1" if r.d > 0 else "H2") if r.typ == "призыв" else "H3"
        if hyp == "H3" and r.t - called.get(key, -10 ** 12) < 7 * DAY:
            continue
        if r.t < last.get((hyp, key), -1):
            continue
        side = 1 if hyp == "H2" else -1
        x = trade(key, ie, tp=None, sl=0.5, hold_h=168, side=side)
        if not x:
            continue
        last[(hyp, key)] = r.t + 7 * DAY
        y = trade(key, ie, tp=0.10, sl=0.25, hold_h=48, side=side)
        pl = []
        for dd in (45, 90, 135):
            j = idx_at(key, r.t - dd * DAY + LAG + 899)
            z = trade(key, j, tp=None, sl=0.5, hold_h=168, side=side) if j is not None and j >= 96 else None
            if z:
                pl.append(z["net"])
        rows.append(dict(hyp=hyp, s=key, ch=r.ch, kind=r.kind, t=r.t, net=x["net"], why=x["why"],
                         n1025=y["net"] if y else np.nan, pre24=c[ip] / c[ip - 96] - 1, imm=c[ie] / c[ip] - 1,
                         qv=float(K[key]["qv"][ip - 96:ip].sum()), pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s137_{per}.pkl")
    print(per, "событий", len(C), "сделок", X.groupby("hyp").size().to_dict() if len(X) else 0)


def line(lab, x, months, cut, col="net"):
    from oi_test import ct  # noqa: E402
    if len(x) < 8:
        return f"  {lab:24s} n={len(x)}"
    m, t, n = ct(x[col], x.t)
    dp = (x[col] - x.pl).dropna()
    md, td, _ = ct(dp, x.t[(x[col] - x.pl).notna()]) if len(dp) >= 8 else (np.nan, np.nan, 0)
    h1, h2 = x[x.t < cut][col].mean(), x[x.t >= cut][col].mean()
    return (f"  {lab:24s} n={n:4d} ({n / months:4.1f}/мес) {m:+.2%} (t {t:+.1f}) в плюсе {(x[col] > 0).mean():.0%} "
            f"стопов {(x.why == 'стоп').mean():.0%} | половины {h1:+.2%} / {h2:+.2%} | сверх плацебо {md:+.2%} (t {td:+.1f})")


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (t0, t1, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s137_{per}.pkl"); X["per"] = per; X["cut"] = ts(cut)
        A.append(X)
        months = (ts(t1) - ts(t0)) / (30.4 * DAY)
        print(f"\n{per}:")
        for h in ("H1", "H2", "H3"):
            x = X[X.hyp == h]
            print(line(f"{h} 7 сут", x, months, ts(cut)))
            if h == "H1" and len(x):
                print(line("H1 10/25/48", x.assign(why=""), months, ts(cut), "n1025"))
                print(f"  {'':24s} до поста за 24 ч: медиана {x.pre24.median():+.2%}, среднее {x.pre24.mean():+.2%}; "
                      f"от поста до входа: медиана {x.imm.median():+.2%}")
                for k, y in x.groupby("ch"):
                    if len(y) >= 8:
                        print(line(f"  {k}", y, months, ts(cut)))
                for k, y in x.groupby("kind"):
                    print(line(f"  вид: {k}", y, months, ts(cut)))
    A = pd.concat(A, ignore_index=True)
    print("\nшесть лет:")
    for h in ("H1", "H2", "H3"):
        x = A[A.hyp == h]
        if len(x) < 8:
            print(f"  {h}: n={len(x)}"); continue
        m, t, n = ct(x.net, x.t); dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()])
        print(f"  {h}: n={n} {m:+.2%} (t {t:+.1f}), сверх плацебо {md:+.2%} (t {td:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
