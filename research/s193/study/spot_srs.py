"""s193 — частота «продавца запаса на споте» по спотовой SRS-выборке (`jobs_spot.py`): доля монето-суток с парой
к USDT на споте, эпизоды продаж и покупок по уровням (без двусторонних) на монето-сутки и в месяц на вселенную, доля
в обороте стороны спота, длительность, совпадение с эпизодом той же стороны на перпе в те же сутки (перп — та же
SRS-выборка), давление √ относительно оборота перпа прошлых суток. Только описание и частоты, без доходов."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

D = "/home/user/mc_data/s193"
DAY = 86400
PERS = ["2020–2022", "2022–2024", "2024–2026"]
USIZE = {"2020–2022": 121, "2022–2024": 177, "2024–2026": 268}


def main():
    T = pd.read_pickle(f"{D}/tables.pkl")
    days, bad = T["days"], T["bad"]
    E = pd.read_pickle(f"{D}/episodes.pkl")
    E = E[~E.twoside]
    sp = days[(days.mkt == "spot") & days.tags.str.contains("srs_spot")]
    miss = bad[bad.tags.astype(str).str.contains("srs_spot")] if len(bad) else bad
    PD = {}
    for per in PERS:
        x = pd.read_pickle(f"{C.D}/s183/daily_{per}.pkl")[["s", "d", "qv", "rv"]]
        PD[per] = x.assign(d=x.d + DAY).set_index(["s", "d"])
    print("== Спот SRS: эпизоды продаж / покупок (без двусторонних) на монето-сутки; в месяц на вселенную × доля с парой ==")
    rows = []
    for per in PERS:
        n = int((sp.per == per).sum())
        nm = int((miss.per == per).sum()) if len(miss) else 0
        cover = n / max(n + nm, 1)
        keys = set(zip(sp[sp.per == per].s, sp[sp.per == per].d))
        ee = E[(E.per == per) & (E.mkt == "spot")]
        ee = ee[[k in keys for k in zip(ee.s, ee.d)]].copy()
        qv, rv = [], []
        for r in ee.itertuples():
            try:
                z = PD[per].loc[(r.s, r.d)]
                qv.append(float(z.qv))
                rv.append(float(z.rv))
            except KeyError:
                qv.append(np.nan)
                rv.append(np.nan)
        ee["qv_prev"] = qv
        ee["I_perp"] = np.sqrt(np.array(rv)) * np.sqrt(ee.vtot / ee.qv_prev)
        um = E[(E.per == per) & (E.mkt == "um")]
        cells = []
        for lvl, cond in (("E1", ee.E1), ("E3", ee.E3), ("E10", ee.E10), ("E10 ≥ 10 тыс. $", ee.E10 & (ee.v_det >= 1e4))):
            x = ee[cond]
            s, b = x[x.side < 0], x[x.side > 0]
            f = lambda k: k / max(n, 1) * USIZE[per] * cover * 30.4
            ucd = s.groupby(["s", "d"]).ngroups
            cells.append(f"{lvl}: {len(s) / max(n, 1):.3f}/{len(b) / max(n, 1):.3f} → {f(len(s)):.0f}/{f(len(b)):.0f} в мес "
                         f"(продажи, монето-суток {f(ucd):.0f})")
            if lvl == "E10 ≥ 10 тыс. $":
                # совпадение с эпизодом продаж на перпе в те же сутки и пересечение по времени
                same = 0
                for r in s.itertuples():
                    z = um[(um.s == r.s) & (um.d == r.d) & (um.side < 0) & (um.t0 < r.t1) & (um.t1 > r.t0)]
                    same += len(z) > 0
                rows.append(dict(per=per, n=n, cover=cover, sells=len(s), buys=len(b), per_month=f(ucd),
                                 share_med=float(s.sh_side.median()) if len(s) else np.nan,
                                 dur_med=float(s.dur.median()) if len(s) else np.nan,
                                 I_med=float(s.I_perp.median()) if len(s) else np.nan,
                                 same_perp=same / max(len(s), 1)))
        print(f"  {per} (монето-суток со спотом {n}, пары нет {nm}, охват {cover:.0%}): " + "; ".join(cells))
    R = pd.DataFrame(rows)
    print("\n== Г «продавец запаса на споте» (E10, ≥ 10 тыс. $ к обнаружению) ==")
    for r in R.itertuples():
        print(f"  {r.per}: продаж {r.sells} (покупок {r.buys}) на {r.n} монето-суток → {r.per_month:.0f} в месяц; доля в продажах "
              f"спота медиана {r.share_med:.0%}; длительность медиана {r.dur_med:.0f} мин; давление √ к перпу медиана "
              f"{r.I_med:.2%}; одновременно эпизод продаж на перпе {r.same_perp:.0%}")
    x = E[(E.mkt == "spot") & E.tags.str.contains("srs_spot") & E.E1]
    print(f"\nдоля эпизода E1 в обороте стороны (спот SRS): медиана {x.sh_side.median():.1%}, p90 {x.sh_side.quantile(.9):.1%}; "
          f"шаг медиана {x.med.median():.1f} с; часть ${x.vchild.median():,.0f}")


if __name__ == "__main__":
    main()
