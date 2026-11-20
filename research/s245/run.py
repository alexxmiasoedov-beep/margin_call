"""s245 — «глубокий стакан» (метод — ВЫВОДЫ.md, записан до расчёта). Шаг 1 по периоду (свечи — через MC_K/MC_F, как s117):
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 <repo>/research/s245/run.py P1
  python3 <repo>/research/s245/run.py P2
— сделки шорта 72 ч, стоп 25% у всех монет во все дни сигнала → s245_trades_<P>.pkl. Шаг 2 — итог по обоим периодам:
  python3 <repo>/research/s245/run.py pool
Запуск из /home/user/mc_data."""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
WEEK, DAY = 7 * 86400, 86400


def trades(P):
    sys.path.insert(0, os.path.join(HERE, "..", "s187"))
    import fastbt as FB  # noqa: E402
    U = set(json.load(open(f"s245/universe_{P}.json")))
    F = pd.read_pickle(f"s245/feat_{P}.pkl")
    F = F[F.s.isin(U)].copy()
    F["B"] = F.b5 - F.b1; F["A"] = F.a5 - F.a1
    F["D"] = (F.B - F.A) / (F.B + F.A)
    F["S"] = (F.b1 - F.a1) / (F.b1 + F.a1)
    F["T"] = ((pd.to_datetime(F.d, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()).astype(np.int64)
    out = []
    for s, g in F.groupby("s"):
        if s not in FB.K:
            continue
        t = FB.K[s]["t"].astype(np.int64)
        lo, _ = FB.live(s)
        I = np.searchsorted(t, g["T"].values - 900)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == g["T"].values - 900)
        ok &= g["T"].values - 900 >= lo + 30 * DAY                  # фьючерсу больше 30 сут
        g, I = g[ok].copy(), I[ok]
        if not len(g):
            continue
        okt, net, stp, bars, tend = FB.trades(s, I, 0.25, 72, -1)
        g["net"] = np.where(okt, net, np.nan); g["stop"] = np.where(okt, stp, False)
        g["hed"] = g.net.values + FB.alt_mv(t[I] + 900, tend)
        out.append(g)
    R = pd.concat(out, ignore_index=True)
    R = R[R.net.notna() & R.hed.notna()]
    R["per"] = P
    R.to_pickle(f"s245_trades_{P}.pkl")
    print(P, "сделок (все монеты, все дни):", len(R), "дней", R.d.nunique(), "монет", R.s.nunique())


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, np.int64) // WEEK); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def pool():
    R = pd.concat([pd.read_pickle(f"s245_trades_{P}.pkl") for P in ("P1", "P2")], ignore_index=True)
    R["mon"] = pd.to_datetime(R["T"], unit="s").dt.to_period("M").astype(str)
    # квинтили внутри дня (нужно ≥ 50 монет в срезе)
    n_day = R.groupby(["per", "d"]).s.transform("size")
    R = R[n_day >= 50].copy()
    for k in ("D", "S"):
        R[f"q{k}"] = R.groupby(["per", "d"])[k].transform(lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
    # плацебо: шорт той же монеты в другие дни сигнала того же месяца (с хеджем)
    g = R.groupby(["s", "mon"]).hed
    R["pl"] = (g.transform("sum") - R.hed) / (g.transform("count") - 1).replace(0, np.nan)
    months = {P: R[R.per == P].d.nunique() * 3 / 30.44 for P in ("P1", "P2")}

    def line(X, P=None):
        m, t, n = ct(X.hed, X["T"]); mr, tr, _ = ct(X.net, X["T"]); md, td, _ = ct(X.hed - X.pl, X["T"])
        mo = months[P] if P else sum(months.values())
        half = ""
        if P:
            mid = X["T"].median()
            half = f"; половины {X[X['T'] < mid].hed.mean():+.2%} / {X[X['T'] >= mid].hed.mean():+.2%}"
        return (f"n={n} ({n / mo:.0f} в мес.), с хеджем {m:+.2%} (t {t:+.1f}), без хеджа {mr:+.2%} (t {tr:+.1f}), "
                f"сверх плацебо {md:+.2%} (t {td:+.1f}), стопов {X.stop.mean():.0%}{half}")
    print("== основное: шорт верхней пятой части по D (глубокие заявки на покупку) ==")
    res = {}
    for P in ("P1", "P2"):
        X = R[(R.per == P) & (R.qD == 4)]
        res[P] = ct(X.hed, X["T"])[0]
        print(f"{P}: {line(X, P)}")
    X = R[R.qD == 4]
    m, t, n = ct(X.hed, X["T"]); md, _, _ = ct(X.hed - X.pl, X["T"])
    print(f"вместе: {line(X)}")
    ok = all(v > 0 for v in res.values()) and t >= 3 and md > 0
    print("порог: " + ("ПРОЙДЕН" if ok else "не пройден") + f" (P1 {res['P1']:+.2%}, P2 {res['P2']:+.2%}, t {t:+.1f}, сверх плацебо {md:+.2%})")
    print("\n== для отчёта ==")
    for k, lab in (("D", "глубокий перекос"), ("S", "мелкий перекос")):
        for P in ("P1", "P2"):
            Y = R[R.per == P]
            q = Y.groupby(f"q{k}").hed.mean()
            top, bot = Y[Y[f"q{k}"] == 4], Y[Y[f"q{k}"] == 0]
            w = pd.concat([top.assign(sgn=1), bot.assign(sgn=-1)])
            sp = w.assign(x=w.hed * w.sgn).groupby(w["T"] // WEEK).x.sum() / w.groupby(w["T"] // WEEK).size() * 2
            print(f"{lab} {P}: шорт по пятым частям (снизу вверх) " + " / ".join(f"{v:+.2%}" for v in q.values)
                  + f"; верх − низ {top.hed.mean() - bot.hed.mean():+.2%}")
    X = R[(R.qD == 4) & (R.qS == 0)]
    for P in ("P1", "P2"):
        print(f"D верх и S низ, {P}: {line(X[X.per == P], P)}")


if __name__ == "__main__":
    pool() if sys.argv[1] == "pool" else trades(sys.argv[1])
