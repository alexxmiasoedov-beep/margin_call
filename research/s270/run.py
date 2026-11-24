"""s270 — «кто ведёт рывок»: лонг рывка перпа (Н1) и шорт рывка розницы (Н2) с выходом внутри дня, по записи ВЫВОДЫ.md.

Запуск по периодам — в папке периода (свечи и фандинг периода через s2/k2y.pkl и s2/fund2y.pkl):
  cd ~/mc_2020 && python3 -I <repo>/research/s270/run.py 2020–2022
  cd ~/mc_oos  && python3 -I <repo>/research/s270/run.py 2022–2024
  cd ~/mc_data && python3 -I <repo>/research/s270/run.py 2024–2026
Сводка трёх периодов: cd ~/mc_data && python3 -I <repo>/research/s270/run.py report
Сделки — /home/user/mc_data/s270_<период>.pkl."""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = "/home/user/mc_data"
SRC = {"2020–2022": "s119_y2020.pkl", "2022–2024": "s119_old.pkl", "2024–2026": "s49/trades.pkl"}
DAY, WEEK, BAR = 86400, 7 * 86400, 900
MAIN = dict(sl=0.10, hold=4)
VARIANTS = [dict(sl=0.10, hold=1), dict(sl=0.10, hold=8), dict(sl=0.10, hold=24), dict(sl=0.05, hold=4), dict(sl=0.15, hold=4)]


def group(share):
    if not np.isfinite(share) or share < 0.10:
        return "P"
    return "S" if share >= 0.26 else "M"


def run(per):
    sys.path.insert(0, os.path.join(HERE, "..", "s187"))
    import fastbt as FB  # noqa: E402  (свечи периода — s2/k2y.pkl в текущей папке)
    X = pd.read_pickle(SRC[per])[["s", "t", "share"]].copy()
    X["t"] = X.t.astype(float).astype(np.int64)
    X["grp"] = [group(float(v)) if v is not None else "P" for v in X.share.values]
    rows = []
    for s, g in X.groupby("s"):
        if s not in FB.K:
            continue
        t = FB.K[s]["t"].astype(np.int64)
        I = np.searchsorted(t, g.t.values - BAR)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == g.t.values - BAR)
        g, I = g[ok], I[ok]
        if not len(g):
            continue
        for grp, side in (("P", 1), ("S", -1), ("M", 1), ("M", -1)):
            m = (g.grp == grp).values
            if not m.any():
                continue
            Ii = I[m]
            for k, par in enumerate([MAIN] + VARIANTS):
                if grp == "M" and k > 0:
                    continue
                okt, net, stp, bars, tend = FB.trades(s, Ii, par["sl"], par["hold"], side)
                te = t[Ii] + BAR
                alt = FB.alt_mv(te, np.where(okt, tend, te))
                pl = FB.placebo(s, Ii, par["sl"], par["hold"], side) if k == 0 else np.full(len(Ii), np.nan)
                for j in range(len(Ii)):
                    if okt[j]:
                        rows.append(dict(s=s, te=int(te[j]), grp=grp, side=side, sl=par["sl"], hold=par["hold"],
                                         net=float(net[j]), stop=bool(stp[j]), hed=float(net[j] - side * alt[j]),
                                         pl=float(pl[j]), share=float(g.share.values[m][j]) if np.isfinite(g.share.values[m][j]) else np.nan))
    R = pd.DataFrame(rows)
    R.to_pickle(f"{OUT}/s270_{per}.pkl")
    print(per, "сделок", len(R), R[(R.sl == 0.10) & (R.hold == 4)].groupby(["grp", "side"]).size().to_dict(), flush=True)


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, np.int64) // WEEK) * WEEK; ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def line(x, mo):
    if len(x) < 5:
        return f"n={len(x)}"
    m, t, n = ct(x.net, x.te); mh, th, _ = ct(x.hed, x.te); md, td, _ = ct(x.net - x.pl, x.te)
    mid = float(np.median(x.te))
    h1, h2 = x[x.te < mid].net.mean(), x[x.te >= mid].net.mean()
    return (f"n={n} ({n / mo:.1f} в мес.), {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; с хеджем {mh:+.2%} "
            f"(t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {x.stop.mean():.0%}")


def report():
    MO = {"2020–2022": 23.8, "2022–2024": 23.8, "2024–2026": 24.5}
    R = {p: pd.read_pickle(f"{OUT}/s270_{p}.pkl") for p in MO}
    for name, grp, side in (("Н1: рывок перпа → лонг", "P", 1), ("Н2: рывок розницы → шорт", "S", -1),
                            ("середина 10–26% → лонг", "M", 1), ("середина 10–26% → шорт", "M", -1)):
        print(f"\n### {name}")
        allx = []
        for p, X in R.items():
            x = X[(X.grp == grp) & (X.side == side)]
            main = x[(x.sl == 0.10) & (x.hold == 4)]
            allx.append(main)
            print(f"  {p}: {line(main, MO[p])}")
            if grp != "M":
                for v in VARIANTS:
                    xv = x[(x.sl == v['sl']) & (x.hold == v['hold'])]
                    if len(xv):
                        m, t, n = ct(xv.net, xv.te)
                        print(f"      стоп {v['sl']:.0%}, {v['hold']} ч: {m:+.2%} (t {t:+.1f}, n={n})")
                if grp == "P":
                    a = main[main.share.notna()]; b = main[main.share.isna()]
                    print(f"      доля спота < 10%: {line(a, MO[p])}")
                    print(f"      спота нет: {line(b, MO[p])}")
        A = pd.concat(allx)
        m, t, n = ct(A.net, A.te); mh, th, _ = ct(A.hed, A.te)
        print(f"  три периода вместе: {m:+.2%} (t {t:+.1f}, n={n}); с хеджем {mh:+.2%} (t {th:+.1f})")


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report()
    else:
        run(sys.argv[1])
