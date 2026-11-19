"""s193 — эпизоды на споте (сутки контроля заводов −7 сут и сутки заводов 🐋): частота продаж и покупок по уровням, доля
в обороте стороны спота против фьючерса тех же суток, длительность. Оценка частоты для гипотезы «продавец запаса на
споте» (база — сутки контроля, ≈ случайные сутки монет с токеном ERC-20). Доходы не считаются."""
import numpy as np
import pandas as pd

D = "/home/user/mc_data/s193"
PERS = ["2020–2022", "2022–2024", "2024–2026"]
USIZE = {"2020–2022": 121, "2022–2024": 177, "2024–2026": 268}


def main():
    T = pd.read_pickle(f"{D}/tables.pkl")
    days = T["days"]
    E = pd.read_pickle(f"{D}/episodes.pkl")
    E = E[~E.twoside]
    for name, tag in (("контроль (−7 сут)", "whale_ctl"), ("сутки завода", "whale")):
        print(f"\n== Спот, {name}: эпизодов на монето-сутки (продажи / покупки) и в месяц на вселенную ==")
        for per in PERS:
            dd = days[(days.per == per) & (days.mkt == "spot")]
            dd = dd[[tag in t.split(",") for t in dd.tags]]
            keys = set(zip(dd.s, dd.d))
            n = len(keys)
            ee = E[(E.per == per) & (E.mkt == "spot")]
            ee = ee[[k in keys for k in zip(ee.s, ee.d)]]
            cells = []
            for lvl, cond in (("E1", ee.E1), ("E3", ee.E3), ("E10", ee.E10),
                              ("E10 и ≥ 10 тыс. $", ee.E10 & (ee.v_det >= 1e4))):
                x = ee[cond]
                s, b = (x.side < 0).sum(), (x.side > 0).sum()
                cells.append(f"{lvl}: {s / n:.3f}/{b / n:.3f} ({s / n * USIZE[per] * 30.4:.0f}/{b / n * USIZE[per] * 30.4:.0f} в мес)")
            print(f"  {per} (n={n}): " + "; ".join(cells))
    print("\n== Доля эпизода E1 в обороте своей стороны: спот против фьючерса (все сутки 🐋 и контроля), медиана / p90 ==")
    for per in PERS:
        for mkt in ("spot", "um"):
            x = E[(E.per == per) & (E.mkt == mkt) & E.E1 & E.tags.str.contains("whale")]
            print(f"  {per} {mkt}: n={len(x)}; доля {x.sh_side.median():.1%} / {x.sh_side.quantile(.9):.1%}; длительность "
                  f"{x.dur.median():.0f} мин; часть ${x.vchild.median():,.0f}")
    # оборот спота к перпу в те же сутки
    sp = days[days.mkt == "spot"][["s", "d", "vol"]].rename(columns={"vol": "vs"})
    um = days[days.mkt == "um"][["s", "d", "vol"]].rename(columns={"vol": "vu"})
    m = sp.merge(um, on=["s", "d"])
    print(f"\nоборот тейкеров спота к перпу в те же сутки (медиана): {np.median(m.vs / m.vu):.2f} (n={len(m)})")


if __name__ == "__main__":
    main()
