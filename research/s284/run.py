"""s284 — внутридневной двойник 🐋 по записи ВЫВОДЫ.md (коммит d1e3a59): события 🐋 из s202 (вид «single»), спокойный
рынок ±5%, шорт 8 ч со стопом 10% (и 4 / 12 ч, 24 ч со стопом 25% — для отчёта).

Запуск из /home/user/mc_data (свечи старых периодов — MC_K / MC_F, как s202):
  python3 -I <repo>/research/s284/run.py 2024–2026
  MC_K=s117/k_oos.pkl MC_F=s117/fund_oos.pkl python3 -I <repo>/research/s284/run.py 2022–2024
  MC_K=s117/k_2020.pkl MC_F=s117/fund_2020.pkl python3 -I <repo>/research/s284/run.py 2020–2022
  python3 -I <repo>/research/s284/run.py report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s187", "s182", "s202"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY, WEEK = "/home/user/mc_data", 86400, 7 * 86400
EXITS = (("8 ч", 8, 0.10), ("4 ч", 4, 0.10), ("12 ч", 12, 0.10), ("24 ч (🐋)", 24, 0.25))
MAIN = "8 ч"


def run(per):
    import fastbt as FB  # noqa: E402
    import common182 as C  # noqa: E402
    from run import deposits, events  # noqa: E402  (s202/run.py)
    K = FB.K
    t0, t1 = C.ts(C.PER[per][0]), C.ts(C.PER[per][1])
    E = events(deposits("main"))
    E = E[E.kind == "single"].copy()
    E["entry"] = (np.ceil((E.tb + 900) / 900) * 900).astype(np.int64)
    E = E[(E.entry >= t0) & (E.entry < t1)]
    rows = []
    for s, g in E.groupby("perp"):
        if s not in K:
            continue
        t = K[s]["t"].astype(np.int64)
        c = K[s]["c"].astype(float)
        lo, _ = FB.live(s)
        g = g.sort_values("entry")
        st = g.entry.values - 900
        I = np.searchsorted(t, st)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == st) & (I >= 96)
        ok &= t[np.minimum(I, len(t) - 1)] >= lo + DAY
        g, I = g[ok], I[ok]
        if not len(g):
            continue
        r24 = c[I] / c[I - 96] - 1
        calm = np.abs(r24) <= 0.05
        g, I = g[calm], I[calm]
        if not len(g):
            continue
        for lab, hold, sl in EXITS:
            okt, net, stp, bars, tend = FB.trades(s, I, sl, hold, -1)
            alt = FB.alt_mv(t[I] + 900, np.where(okt, tend, t[I] + 900))
            pl = FB.placebo(s, I, sl, hold, -1, days=(7, 14, 21))
            for j, e in enumerate(g.entry.values):
                if okt[j]:
                    rows.append(dict(ex=lab, s=s, t=int(e), net=float(net[j]), stop=bool(stp[j]),
                                     hed=float(net[j] + alt[j]), pl=float(pl[j])))
    R = pd.DataFrame(rows)
    R.to_pickle(f"{OUT}/s284_{per}.pkl")
    print(per, R.groupby("ex").size().to_dict(), flush=True)


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
    sys.path.insert(0, os.path.join(HERE, "..", "s182"))
    import common182 as C  # noqa: E402
    R = {p: pd.read_pickle(f"{OUT}/s284_{p}.pkl") for p in C.PER if os.path.exists(f"{OUT}/s284_{p}.pkl")}
    for lab, _, _ in EXITS:
        print(f"\n### выход {lab}{' — основной' if lab == MAIN else ''}")
        allx, signs = [], []
        for p, X in R.items():
            x = X[X.ex == lab]
            m, t, n = ct(x.net, x.t)
            mh, th, _ = ct(x.hed, x.t)
            md, td, _ = ct(x.net - x.pl, x.t)
            mid = float(np.median(x.t))
            h1, h2 = x[x.t < mid].net.mean(), x[x.t >= mid].net.mean()
            mo = C.months(p)
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
            m, t, n = ct(A.net, A.t)
            mh, th, _ = ct(A.hed, A.t)
            ok = all(signs) and t >= 3
            print(f"  вместе: {m:+.2%} (t {t:+.1f}, n={n}); с хеджем {mh:+.2%} (t {th:+.1f}); плюс во всех — "
                  f"{'да' if all(signs) else 'нет'} → {'ПОРОГ ТРЁХ ПЕРИОДОВ ПРОЙДЕН' if ok else 'не пройден'}")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
