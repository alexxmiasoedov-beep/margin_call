"""s285 — внутридневной двойник 🔝 по записи ВЫВОДЫ.md (коммит dbf0c07).

Запуск из /home/user/mc_data (свечи старых периодов — MC_K / MC_F, как s185):
  python3 -I <repo>/research/s285/run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 -I <repo>/research/s285/run.py 2022–2024
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 -I <repo>/research/s285/run.py 2020–2022
  python3 -I <repo>/research/s285/run.py report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
D = "/home/user/mc_data"
WIN = {"2020–2022": ("2020-10-01", "2022-10-01"), "2022–2024": ("2022-10-01", "2024-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-19")}
EXITS = (("8 ч", 0.10, 8), ("4 ч", 0.10, 4), ("24 ч", 0.10, 24))
MAIN = "8 ч"
BAR, DAY, WEEK = 900, 86400, 7 * 86400
MONTH = 30.44 * DAY


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


def kt_events(per):
    if per == "2024–2026":
        X = pd.read_pickle(f"{D}/s65/trades.pkl")[["s", "t"]].copy()
        X["t"] = X.t.astype(float).astype(np.int64)
        return X
    sys.path.insert(0, os.path.join(HERE, "..", "s185"))
    sys.path.insert(0, os.path.join(HERE, "..", "s43"))
    import oos as O  # noqa: E402
    from common import K, live  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    Vu, Vb = O.volumes(per, "upbit"), O.volumes(per, "bithumb")
    ev, majors = O.events(Vu.add(Vb, fill_value=0.0).fillna(0.0), per, K, live, idx_at)
    print(per, "🔝: лидеры", majors, "входов", len(ev), flush=True)
    return pd.DataFrame(ev, columns=["s", "t"]).astype({"t": np.int64})


def run(per):
    sys.path.insert(0, os.path.join(HERE, "..", "s187"))
    import fastbt as FB  # noqa: E402
    t0, t1 = ts(WIN[per][0]), ts(WIN[per][1])
    X = kt_events(per)
    X = X[(X.t >= t0) & (X.t < t1)]
    rows = []
    for s, g in X.groupby("s"):
        if s not in FB.K:
            continue
        t = FB.K[s]["t"].astype(np.int64)
        I = np.searchsorted(t, g.t.values - BAR)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == g.t.values - BAR)
        I = I[ok]
        if not len(I):
            continue
        te = t[I] + BAR
        for lab, sl, hold in EXITS:
            okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, -1)
            alt = FB.alt_mv(te, np.where(okt, tend, te))
            pl = FB.placebo(s, I, sl, hold, -1, days=(7, 14, 21))
            for j in range(len(I)):
                if okt[j]:
                    rows.append(dict(ex=lab, s=s, te=int(te[j]), net=float(net[j]), stop=bool(stp[j]),
                                     hed=float(net[j] + alt[j]), pl=float(pl[j])))
    R = pd.DataFrame(rows)
    R.to_pickle(f"{D}/s285_{per}.pkl")
    print(per, "сделок", R.groupby("ex").size().to_dict(), flush=True)


def ct(x, t):
    x = np.asarray(x, float)
    w = (np.asarray(t, np.int64) // WEEK) * WEEK
    ok = np.isfinite(x)
    x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean()
    s = pd.Series(x - m).groupby(w).sum()
    se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def report():
    R = {p: pd.read_pickle(f"{D}/s285_{p}.pkl") for p in WIN if os.path.exists(f"{D}/s285_{p}.pkl")}
    for lab, _, _ in EXITS:
        print(f"\n### 🔝 — выход {lab}{' — основной' if lab == MAIN else ' (для отчёта)'}")
        allx, signs = [], []
        for p, X in R.items():
            x = X[X.ex == lab]
            mo = (ts(WIN[p][1]) - ts(WIN[p][0])) / MONTH
            m, t, n = ct(x.net, x.te)
            mh, th, _ = ct(x.hed, x.te)
            md, td, _ = ct(x.net - x.pl, x.te)
            mid = float(np.median(x.te))
            h1, h2 = x[x.te < mid].net.mean(), x[x.te >= mid].net.mean()
            print(f"  {p}: n={n} ({n / mo:.1f} в мес.), {m:+.2%} (t {t:+.1f}); половины {h1:+.2%} / {h2:+.2%}; "
                  f"с хеджем {mh:+.2%} (t {th:+.1f}); сверх плацебо {md:+.2%} (t {td:+.1f}); стопов {x.stop.mean():.0%}")
            if lab == MAIN and p == "2024–2026":
                conds = (("≥ 20 в мес.", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                         ("сверх плацебо > 0", md > 0), ("с хеджем > 0", mh > 0))
                print("    правило владельца: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds))
            allx.append(x)
            signs.append(m > 0)
        if len(allx) == 3:
            A = pd.concat(allx)
            m, t, n = ct(A.net, A.te)
            mh, th, _ = ct(A.hed, A.te)
            print(f"  вместе: {m:+.2%} (t {t:+.1f}, n={n}); с хеджем {mh:+.2%} (t {th:+.1f}); плюс во всех — "
                  f"{'да' if all(signs) else 'нет'} → {'ПОРОГ ТРЁХ ПЕРИОДОВ ПРОЙДЕН' if all(signs) and t >= 3 else 'не пройден'}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
