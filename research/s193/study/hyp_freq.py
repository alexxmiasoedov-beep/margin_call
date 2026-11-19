"""s193 — частоты гипотез (без доходов): правило обнаружения в реальном времени, вход на закрытии первой 15-мин свечи
после обнаружения, доля эпизодов, ещё идущих к входу, остаток длительности после входа, конец эпизода в реальном
времени (нет части дольше max(3·шаг, 5 мин)), ожидаемое давление по закону квадратного корня (σ и оборот —
за предыдущие сутки, до обнаружения), пересечение с входами журналов (та же монета, ±24 ч).

Г1 «скрытый продавец идёт»: эпизод продаж E3 (часть ≥ 100 $, доля в продажах тейкеров от начала до обнаружения ≥ 3%)
   → шорт на закрытии 15-мин свечи после обнаружения, 4 ч (запасной 24 ч); контроль той же формы — эпизод покупок E3.
Г2 «после конца — возврат»: эпизод (любой стороны) с долей в обороте стороны за всю жизнь ≥ 3%, длительностью ≥ 60 мин
   и оборотом ≥ 0,05% суточного оборота перпа прошлых суток; конец — нет части max(3·шаг, 5 мин) → сделка против стороны
   алгоритма на закрытии ближайшей 15-мин свечи, 4 ч (запасной 24 ч); главное — конец покупок → шорт; контроль той же
   формы — конец продаж → лонг (знак обратный).
Г3 «ритм без одинаковых частей»: односторонний ритм D2 (SNR ≥ 50, другая сторона < 5) два часа подряд с одним периодом
   (±2%), без эпизода D1/D1n той же стороны → сделка в сторону ритма на закрытии часа, 4 ч; контроль — то же
   для покупок.
Только частоты и описание; цены после обнаружения не читаются."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

D = "/home/user/mc_data/s193"
DAY = 86400
PERS = ["2020–2022", "2022–2024", "2024–2026"]
USIZE = {"2020–2022": 121, "2022–2024": 177, "2024–2026": 268}


def prev_day_panel():
    out = {}
    for per in PERS:
        x = pd.read_pickle(f"{C.D}/s183/daily_{per}.pkl")[["s", "d", "qv", "rv"]]
        x = x.assign(d=x.d + DAY)          # значения прошлых суток → ключ текущих
        out[per] = x.set_index(["s", "d"])
    return out


def main():
    T = pd.read_pickle(f"{D}/tables.pkl")
    days, d2 = T["days"], T["d2"]
    E = pd.read_pickle(f"{D}/episodes.pkl")
    srs = days[days.tags.str.contains("srs") & (days.mkt == "um")]
    nd = srs.groupby("per").size()
    Es = E[E.srs & (E.mkt == "um")].copy()
    PD = prev_day_panel()
    Es["entry"] = (np.floor(Es.det_t / 900_000) + 1) * 900_000          # закрытие 15-мин свечи после обнаружения
    Es["gap_end"] = np.maximum(3 * Es.med * 1000, 300_000)
    Es["end_rt"] = Es.t1 + Es.gap_end                                    # конец в реальном времени
    Es["running"] = Es.end_rt > Es.entry
    Es["rem"] = (Es.t1 - Es.entry) / 60000
    qv, rv = [], []
    for r in Es.itertuples():
        try:
            z = PD[r.per].loc[(r.s, r.d)]
            qv.append(float(z.qv))
            rv.append(float(z.rv))
        except KeyError:
            qv.append(np.nan)
            rv.append(np.nan)
    Es["qv_prev"] = qv
    Es["sig_prev"] = np.sqrt(np.array(rv))
    Es["Q_frac"] = Es.vtot / Es.qv_prev
    Es["I_sqrt"] = Es.sig_prev * np.sqrt(Es.Q_frac)                      # Y = 1
    Es["sh_life"] = Es.sh_side
    # давление до обнаружения (описание): сдвиг цены от первой части до части в момент обнаружения в сторону
    # алгоритма против прогноза √ по объёму к моменту обнаружения
    Es["a_pre"] = Es.side * (Es.p_det / Es.p_first - 1)
    Es["I_det"] = Es.sig_prev * np.sqrt(Es.v_det / Es.qv_prev)
    print("== Давление до обнаружения: сдвиг цены от первой части до обнаружения в сторону алгоритма ==")
    for per in PERS:
        for lvl in ("E1", "E3", "E10"):
            y = Es[(Es.per == per) & Es[lvl]].dropna(subset=["a_pre", "I_det"])
            if len(y) < 10:
                continue
            se = y.a_pre.std() / np.sqrt(len(y))
            print(f"  {per} {lvl}: n={len(y)}; сдвиг среднее {y.a_pre.mean():+.3%} (t {y.a_pre.mean() / se:.1f}), медиана "
                  f"{y.a_pre.median():+.3%}, в сторону алгоритма {np.mean(y.a_pre > 0):.0%}; прогноз √ медиана "
                  f"{y.I_det.median():.3%}")
    y = Es[Es.E1].dropna(subset=["a_pre", "I_det"]).copy()
    y["qI"] = pd.qcut(y.I_det, 5, labels=False, duplicates="drop")
    g = y.groupby("qI").agg(I=("I_det", "median"), a=("a_pre", "mean"), med=("a_pre", "median"), n=("a_pre", "size"))
    print("  E1 по квинтилям прогноза √ (все периоды): " + "; ".join(
        f"I {r.I:.2%} → сдвиг {r.a:+.2%} (медиана {r.med:+.2%}, n {int(r.n)})" for r in g.itertuples()))
    print()
    print("== Г1: эпизод продаж E3 (контроль — покупок E3); вход — закрытие 15-мин свечи после обнаружения ==")
    for per in PERS:
        n = nd.get(per, 1)
        for side, name in ((-1, "продажи"), (1, "покупки")):
            y = Es[(Es.per == per) & Es.E3 & (Es.side == side)]
            for lvl, yy in (("E3", y), ("E10", y[y.E10])):
                print(f"  {per} {name} {lvl}: в месяц {len(yy) / n * USIZE[per] * 30.4:6.1f}; ещё идут к входу "
                      f"{yy.running.mean():.0%}; остаток после входа мин (медиана / p75) {yy.rem.clip(lower=0).median():.0f} / "
                      f"{yy.rem.clip(lower=0).quantile(.75):.0f}; давление √: медиана {yy.I_sqrt.median():.2%}, p90 "
                      f"{yy.I_sqrt.quantile(.9):.2%}; оборот эпизода к суточному медиана {yy.Q_frac.median():.2%}")
    print("\n== Г1 с порогом размера в реальном времени: оборот к обнаружению ≥ 0,05% / 0,1% суточного оборота прошлых суток ==")
    for per in PERS:
        n = nd.get(per, 1)
        cells = []
        for side, name in ((-1, "продажи"), (1, "покупки")):
            for thr in (0.0005, 0.001):
                y = Es[(Es.per == per) & Es.E3 & (Es.side == side) & (Es.v_det / Es.qv_prev >= thr)]
                cells.append(f"{name} ≥ {thr:.2%}: {len(y) / n * USIZE[per] * 30.4:5.1f} в мес (√ медиана {y.I_sqrt.median():.2%})")
        print(f"  {per}: " + "; ".join(cells))
    print("\n== Г2 с порогом давления в момент конца: I = σ·√(оборот эпизода / суточный) ≥ 0,3% / 0,5% ==")
    for per in PERS:
        n = nd.get(per, 1)
        cells = []
        for side, name in ((1, "конец покупок"), (-1, "конец продаж")):
            for thr in (0.003, 0.005):
                y = Es[(Es.per == per) & (Es.side == side) & (Es.vchild >= 100) & (Es.sh_life >= 0.03) & (Es.dur >= 60)
                       & (Es.I_sqrt >= thr)]
                cells.append(f"{name} I ≥ {thr:.1%}: {len(y) / n * USIZE[per] * 30.4:5.1f} в мес")
        print(f"  {per}: " + "; ".join(cells))
    print("\n== Таймер (шаг 59,5–60,5 с и ≥ 50% частей в одной секунде минуты) среди E1: доля и частота ==")
    for per in PERS:
        n = nd.get(per, 1)
        y = Es[(Es.per == per) & Es.E1]
        tm = (y.med >= 59.5) & (y.med <= 60.5) & (y.smode >= 0.5)
        print(f"  {per}: таймер {tm.mean():.0%} эпизодов E1 ({tm.sum() / n * USIZE[per] * 30.4:.1f} в мес); продаж среди таймера "
              f"{np.mean(y[tm].side < 0):.0%}; длительность таймера медиана {y[tm].dur.median():.0f} мин, прочих "
              f"{y[~tm].dur.median():.0f} мин")
    print("\n== Г2: конец крупного алгоритма (доля за жизнь ≥ 3%, ≥ 60 мин, оборот ≥ 0,05% суточного) ==")
    for per in PERS:
        n = nd.get(per, 1)
        for side, name in ((1, "конец покупок → шорт"), (-1, "конец продаж → лонг (контроль)")):
            y = Es[(Es.per == per) & (Es.side == side) & (Es.vchild >= 100) & (Es.sh_life >= 0.03) & (Es.dur >= 60)
                   & (Es.Q_frac >= 0.0005)]
            edge = y.edge.mean() if len(y) else np.nan
            print(f"  {per} {name}: в месяц {len(y) / n * USIZE[per] * 30.4:6.1f}; длительность медиана {y.dur.median():.0f} мин;"
                  f" оборот к суточному медиана {y.Q_frac.median():.2%}; давление √ медиана {y.I_sqrt.median():.2%};"
                  f" у края суток (конец не виден) {edge:.0%}")
    # Г3: ритм
    print("\n== Г3: односторонний ритм два часа подряд без эпизода D1/D1n той же стороны ==")
    x = d2[d2.tags.str.contains("srs") & (d2.mkt == "um") & (d2.snr >= 50) & (d2.snr_oth < 5)].copy()
    for per in PERS:
        n = nd.get(per, 1)
        y = x[x.per == per].sort_values(["s", "d", "side", "h"])
        ev = []
        for (s, d, side), g in y.groupby(["s", "d", "side"]):
            hs = g.h.values
            ps = g.period.values
            for i in range(1, len(hs)):
                if hs[i] == hs[i - 1] + 1 and abs(ps[i] / ps[i - 1] - 1) <= 0.02:
                    h0 = d * 1000 + hs[i - 1] * 3_600_000
                    e = Es[(Es.s == s) & (Es.d == d) & (Es.side == side) & (Es.t0 < h0 + 7_200_000) & (Es.t1 > h0)]
                    ev.append(dict(s=s, d=d, side=side, h=hs[i], period=ps[i], d1=len(e) > 0))
                    break
        ev = pd.DataFrame(ev)
        if not len(ev):
            print(f"  {per}: событий нет")
            continue
        free = ev[~ev.d1]
        print(f"  {per}: событий {len(ev)} (в месяц {len(ev) / n * USIZE[per] * 30.4:.1f}); без D1/D1n {len(free)} "
              f"(в месяц {len(free) / n * USIZE[per] * 30.4:.1f}; продаж {np.mean(free.side < 0):.0%}); периоды: "
              + ", ".join(f"{k:g}" for k in np.round(free.period, 1).value_counts().head(6).index))
    # пересечение с журналами
    print("\n== Пересечение Г1 (E3, обе стороны) с входами журналов той же монеты в ±24 ч ==")
    for per in PERS:
        Jr = C.journals(per)
        y = Es[(Es.per == per) & Es.E3]
        if not len(y):
            continue
        jt = {s: np.sort(g.t.values) for s, g in Jr.groupby("s")}
        hit = []
        for r in y.itertuples():
            a = jt.get(r.s)
            t = r.det_t / 1000
            hit.append(a is not None and np.any(np.abs(a - t) <= DAY))
        print(f"  {per}: E3 эпизодов {len(y)}; с входом журнала в ±24 ч {np.mean(hit):.1%}")
    pd.to_pickle(Es, f"{D}/episodes_rt.pkl")


if __name__ == "__main__":
    main()
