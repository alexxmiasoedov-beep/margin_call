"""s154b — признаки F3 (дельта 4 свечей) и F4 (расхождение цены и дельты) на свече пампа во всех трёх периодах
(гипотеза — ВЫВОДЫ.md). Пампы: 2020–2022 — s119_y2020.pkl, 2022–2024 — s119_old.pkl (папки периодов), 2024–2026 —
s49/trades.pkl. Запуск в папке периода с MC_K/MC_F: python3 <repo>/research/s154/pumps_old.py <период>;
сводка из /home/user/mc_data: python3 … report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = "/home/user/mc_data"
SRC = {"2020–2022": "s119_y2020.pkl", "2022–2024": "s119_old.pkl", "2024–2026": "s49/trades.pkl"}
CUTS = {"2020–2022": "2021-10-01", "2022–2024": "2023-10-01", "2024–2026": "2025-12-01"}


def run(per):
    import feat  # noqa: E402  (свечи периода — через MC_K)
    X = pd.read_pickle(SRC[per])
    rows = []
    for r in X.itertuples():
        f = feat.features(r.s, int(r.t))
        if f:
            rows.append(dict(s=r.s, t=int(r.t), net=float(r.net), share=float(r.share) if pd.notna(r.share) else np.nan, **f))
    F = pd.DataFrame(rows)
    F.to_pickle(f"{OUT}/s154_pumps_{per}.pkl")
    print(per, len(F), "пампов")


def report():
    sys.path.insert(0, os.path.join(HERE, "..", "s43"))
    from oi_test import ct  # noqa: E402
    from pick import diff  # noqa: E402
    A = []
    for per in SRC:
        F = pd.read_pickle(f"{OUT}/s154_pumps_{per}.pkl").rename(columns={"t": "te"}); F["per"] = per
        F["low3"] = F.F3 < F.F3.median(); A.append(F)
        c = int(pd.Timestamp(CUTS[per], tz="UTC").timestamp())
        print(f"\n{per}: пампов {len(F)}, шорт 10/25/48 всех {F.net.mean():+.2%}")
        for name, col in (("расхождение F4", "F4"), ("дельта 4 свечей ниже медианы F3", "low3")):
            m = F[col].astype(bool); k, d = F[m], F[~m]
            dd, t = diff(k, d); mk, tk, nk = ct(k.net, k.te)
            print(f"  {name}: с признаком {nk} ({mk:+.2%}, t {tk:+.1f}; половины {k[k.te < c].net.mean():+.2%} / "
                  f"{k[k.te >= c].net.mean():+.2%}), без {len(d)} ({d.net.mean():+.2%}), разница {dd:+.2%} (t {t:+.1f})")
        sp = F[F.share >= 0.26]
        if len(sp) >= 30:
            m = sp.F4.astype(bool)
            print(f"  внутри пампов со спотом ≥ 26%: с расхождением {int(m.sum())} {sp[m].net.mean():+.2%}, без {int((~m).sum())} {sp[~m].net.mean():+.2%}")
    A = pd.concat(A, ignore_index=True)
    m = A.F4.astype(bool); dd, t = diff(A[m], A[~m]); mk, tk, nk = ct(A[m].net, A[m].te)
    print(f"\nшесть лет: с расхождением {nk} ({mk:+.2%}, t {tk:+.1f}), разница с остальными {dd:+.2%} (t {t:+.1f})")


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
