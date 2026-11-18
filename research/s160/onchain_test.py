"""s160 — шорт после крупного завода токена на биржу (гипотеза — ВЫВОДЫ.md, записана до расчёта). События — s160_events.pkl
(events.py). Вход — закрытие первой 15-мин свечи не раньше чем через 15 мин после блока; 24 ч (основная) и 48 ч, стоп 25%;
хедж индексом альтов; плацебо — та же монета за 45/90/135 сут. Запуск в папке периода с MC_K/MC_F/MC_CUT:
python3 <repo>/research/s160/onchain_test.py <период>; сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s141"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
OUT, DAY = "/home/user/mc_data", 86400
PER = {"2020–2022": ("2020-10-01", "2022-10-01", "2021-10-01"), "2022–2024": ("2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": ("2024-10-01", "2026-10-17", "2025-12-01")}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def run(per):
    from common import K, live, trade  # noqa: E402
    from oi_test import idx_at  # noqa: E402
    from flow_test import alt_index  # noqa: E402
    t0, t1 = ts(PER[per][0]), ts(PER[per][1])
    T_, I_ = alt_index(K)

    def mv(a, b):
        i = int(np.searchsorted(T_, a - 900, "right")) - 1; j = int(np.searchsorted(T_, b - 900, "right")) - 1
        return I_[j] / I_[i] - 1 if 0 <= i <= j < len(I_) else np.nan

    E = pd.read_pickle(f"{OUT}/s160_events.pkl")
    E = E[(E.first_all | E.first_clean)]
    rows = []
    for r in E.itertuples():
        te = int(-(-(int(r.t) + 900) // 900) * 900)
        if not (t0 <= te < t1) or r.perp not in K:
            continue
        lo, hi = live(r.perp)
        if not np.isfinite(lo) or te < lo + DAY:
            continue
        i = idx_at(r.perp, te)
        if i is None or int(K[r.perp]["t"][i]) + 900 != te:
            continue
        x = trade(r.perp, i, tp=None, sl=0.25, hold_h=24, side=-1)
        if not x:
            continue
        y = trade(r.perp, i, tp=None, sl=0.25, hold_h=48, side=-1)
        t_end = int(K[r.perp]["t"][i]) + 900 + int(x["bars"]) * 900
        pl = []
        for back in (45, 90, 135):
            j = idx_at(r.perp, te - back * DAY)
            w = trade(r.perp, j, tp=None, sl=0.25, hold_h=24, side=-1) if j is not None else None
            if w:
                pl.append(w["net"])
        rows.append(dict(s=r.perp, t=te, frac=r.frac, exch=r.exch, clean=bool(r.first_clean), all=bool(r.first_all),
                         from_exch=r.from_exch, net=x["net"], why=x["why"], n48=y["net"] if y else np.nan,
                         hed=x["net"] + mv(te, t_end), pl=np.mean(pl) if pl else np.nan))
    X = pd.DataFrame(rows)
    X.to_pickle(f"{OUT}/s160_{per}.pkl")
    print(per, "сделок", len(X), "чистых", int(X.clean.sum()) if len(X) else 0, flush=True)


def report():
    from oi_test import ct  # noqa: E402
    A = []
    for per, (a, b, cut) in PER.items():
        X = pd.read_pickle(f"{OUT}/s160_{per}.pkl"); X["per"] = per; A.append(X)
        months = (ts(b) - ts(a)) / (30.4 * DAY); c = ts(cut)
        print(f"\n{per}:")
        for name, x in (("чистые ≥ 0,5% (основная)", X[X.clean]), ("все заводы ≥ 0,5%", X[X["all"]]),
                        ("чистые ≥ 1%", X[X.clean & (X.frac >= 0.01)]), ("чистые на Binance", X[X.clean & (X.exch == "Binance")]),
                        ("перекладка (с биржи)", X[X["all"] & (X.from_exch == True)])):  # noqa: E712
            if len(x) < 8:
                print(f"  {name:26s} n={len(x)}"); continue
            m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
            m48, t48, _ = ct(x.n48.dropna(), x.t[x.n48.notna()])
            dp = (x.net - x.pl).dropna(); md, td, _ = ct(dp, x.t[(x.net - x.pl).notna()])
            print(f"  {name:26s} n={n:5d} ({n / months:5.1f}/мес) 24 ч {m:+.2%} (t {t:+.1f}) | половины {x[x.t < c].net.mean():+.2%} / "
                  f"{x[x.t >= c].net.mean():+.2%} | с хеджем {mh:+.2%} (t {th:+.1f}) | 48 ч {m48:+.2%} (t {t48:+.1f}) | "
                  f"сверх плацебо {md:+.2%} (t {td:+.1f}) | стопов {(x.why == 'стоп').mean():.0%}")
    A = pd.concat(A, ignore_index=True); x = A[A.clean]
    m, t, n = ct(x.net, x.t); mh, th, _ = ct(x.hed.dropna(), x.t[x.hed.notna()])
    print(f"\nшесть лет, чистые: n={n} {m:+.2%} (t {t:+.1f}), с хеджем {mh:+.2%} (t {th:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
