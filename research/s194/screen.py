"""s194 — отбор Г2 «информированный продавец» и Г3 «возврат временного давления» на фьючерсной SRS-выборке s193
(правила и пороги — ВЫВОДЫ.md, записаны до расчёта).

Г2: первый прогон перпа за сутки на сторону, который в момент своего обнаружения проходит: часть ≥ 100 $, доля в обороте
тейкеров своей стороны от начала ≥ 3%, исполнено (часть × число частей) ≥ 0,1% оборота перпа прошлых суток, не двусторонний
в реальном времени → сделка в сторону алгоритма (продажи → шорт, покупки → лонг) на закрытии 15-мин свечи после
обнаружения, 4 ч (запасной 24 ч), стоп 15%.
Г3: конец прогона (доля за жизнь ≥ 3%, ≥ 60 мин, часть ≥ 100 $, оборот ≥ 0,05% оборота перпа прошлых суток, не у края
суток, не двусторонний по полным суткам) → сделка против стороны алгоритма на закрытии 15-мин свечи после
«последняя часть + max(3·шаг, 5 мин)», 4 ч (запасной 24 ч), стоп 15%; вариант I = σ·√(оборот / оборот суток) ≥ 0,3%.
Плацебо — та же монета 7 сут назад (основное) и 45/90/135 сут; хедж — индекс альтов s103.

Запуск из /home/user/mc_data: [MC_K=… MC_F=…] python3 <repo>/research/s194/screen.py <период>  → s194/screen_<период>.pkl;
сводка: … screen.py report"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s187"))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))

DAY, OUT = 86400, "/home/user/mc_data"
D193, D194 = f"{OUT}/s193", f"{OUT}/s194"
USIZE = {"2020–2022": 121, "2022–2024": 177, "2024–2026": 268}
LOG13 = np.log(1.3)


def prev_day(per):
    x = pd.read_pickle(f"{OUT}/s183/daily_{per}.pkl")[["s", "d", "qv", "rv"]]
    return x.assign(d=x.d + DAY).set_index(["s", "d"])          # значения прошлых суток → ключ текущих


def runs(per):
    T = pd.read_pickle(f"{D193}/tables.pkl")
    R, days = T["runs"], T["days"]
    srs_days = days[(days.mkt == "um") & days.tags.str.contains("srs") & (days.per == per)]
    R = R[(R.mkt == "um") & R.tags.str.contains("srs") & (R.per == per) & R.det_t.notna()].copy().reset_index(drop=True)
    P = prev_day(per)
    z = P.reindex(list(zip(R.s, R.d)))
    R["qv_prev"], R["rv_prev"] = z.qv.values, z.rv.values
    R["v_det"] = R.vchild * R.n_det
    return R, len(srs_days)


def two_rt(R, entry):
    """Двусторонний в реальном времени: прогон другой стороны с частью ±30%, обнаруженный не позже входа, после начала
    нашего прогона и начавшийся до обнаружения нашего."""
    out = np.zeros(len(R), bool)
    for _, g in R.groupby(["s", "d"]):
        if g.side.nunique() < 2:
            continue
        ix = g.index.values
        sd, vc, t0, dt = g.side.values, g.vchild.values, g.t0.values, g.det_t.values
        en = entry[ix]
        for a in range(len(ix)):
            o = (sd != sd[a]) & (np.abs(np.log(vc / vc[a])) <= LOG13) & (dt <= en[a]) & (dt > t0[a]) & (t0 < dt[a])
            out[ix[a]] = o.any()
    return out


def two_full(R):
    """Двусторонний по полным суткам (как s193): прогон другой стороны с частью ±30%, пересекающийся по времени."""
    out = np.zeros(len(R), bool)
    for _, g in R.groupby(["s", "d"]):
        if g.side.nunique() < 2:
            continue
        ix = g.index.values
        sd, vc, t0, t1 = g.side.values, g.vchild.values, g.t0.values, g.t1.values
        for a in range(len(ix)):
            o = (sd != sd[a]) & (np.abs(np.log(vc / vc[a])) <= LOG13) & (np.minimum(t1, t1[a]) > np.maximum(t0, t0[a]))
            out[ix[a]] = o.any()
    return out


def events(per):
    R, nd = runs(per)
    # Г2
    entry2 = ((np.floor(R.det_t.values / 9e5) + 1) * 9e5).astype(np.int64)
    R["two_rt"] = two_rt(R, entry2)
    R["entry2"] = entry2
    q2 = (R.vchild >= 100) & (R.sh_det >= 0.03) & (R.v_det >= 0.001 * R.qv_prev) & ~R.two_rt
    E2 = R[q2].sort_values("det_t").groupby(["s", "d", "side"]).head(1).copy()
    E2["hyp"], E2["entry"], E2["tside"] = "Г2", E2.entry2, E2.side                 # в сторону алгоритма
    # Г3
    R["two_full"] = two_full(R)
    R["end_rt"] = R.t1 + np.maximum(3 * R.med * 1000, 300_000)
    R["entry3"] = ((np.floor(R.end_rt.values / 9e5) + 1) * 9e5).astype(np.int64)
    R["Ip"] = np.sqrt(R.rv_prev) * np.sqrt(R.vtot / R.qv_prev)
    q3 = ((R.vchild >= 100) & (R.sh_side >= 0.03) & (R.dur >= 60) & (R.vtot >= 0.0005 * R.qv_prev) & (R.edge == 0)
          & ~R.two_full)
    E3 = R[q3].sort_values("end_rt").groupby(["s", "d", "side"]).head(1).copy()
    E3["hyp"] = "Г3"
    E3b = R[q3 & (R.Ip >= 0.003)].sort_values("end_rt").groupby(["s", "d", "side"]).head(1).copy()
    E3b["hyp"] = "Г3 I≥0,3%"
    for e in (E3, E3b):
        e["entry"], e["tside"] = e.entry3, -e.side                                   # против алгоритма
    E = pd.concat([E2, E3, E3b], ignore_index=True)
    return E[["hyp", "s", "d", "side", "tside", "entry", "det_t", "t0", "t1", "med", "vchild", "sh_det", "sh_side",
              "v_det", "vtot", "qv_prev", "Ip", "smode", "dur"]], nd


def run(per):
    import fastbt as FB  # noqa: E402
    K = FB.K
    E, nd = events(per)
    rows = []
    for (s, tside), g in E.groupby(["s", "tside"]):
        if s not in K:
            continue
        t = K[s]["t"].astype(np.int64)
        T = (g.entry.values // 1000 - 900).astype(np.int64)                # начало свечи, в закрытие которой вход
        I = np.searchsorted(t, T)
        ok = (I < len(t)) & (t[np.minimum(I, len(t) - 1)] == T) & (I >= 96)
        if not ok.any():
            continue
        gg = g[ok].copy()
        I = I[ok]
        for h in (4, 24):
            okt, net, stp, bars, tend = FB.trades(s, I, 0.15, h, int(tside))
            mv = FB.alt_mv(t[I] + 900, tend)
            gg[f"net{h}"] = np.where(okt, net, np.nan)
            gg[f"hed{h}"] = np.where(okt, net - tside * mv, np.nan)
            gg[f"stop{h}"] = stp
            gg[f"pl{h}"] = FB.placebo(s, I, 0.15, h, int(tside), days=(7,))
            gg[f"plL{h}"] = FB.placebo(s, I, 0.15, h, int(tside))
            ok0, net0, *_ = FB.trades(s, I, 0, h, int(tside))
            gg[f"nos{h}"] = np.where(ok0, net0, np.nan)
        gg["t"] = t[I] + 900
        rows.append(gg)
    X = pd.concat(rows, ignore_index=True)
    X["per"] = per
    X.attrs["nd"] = nd
    X.to_pickle(f"{D194}/screen_{per}.pkl")
    print(per, "монето-суток SRS", nd, X.groupby(["hyp", "tside"]).size().to_dict(), flush=True)


def report():
    import common182 as C  # noqa: E402
    pers = list(C.PER)
    X = {p: pd.read_pickle(f"{D194}/screen_{p}.pkl") for p in pers}
    print("Отбор Г2 и Г3 на фьючерсной SRS-выборке s193. Доход на сделку после комиссии 0,1% и фандинга; стоп 15%.\n"
          "Порог отбора: три периода вместе — среднее ≥ +0,15%, t ≥ 1,5; в плюсе ≥ 2 периодов из 3.\n")
    variants = [("Г2", "продажи → шорт", lambda x: x.side < 0), ("Г2", "покупки → лонг", lambda x: x.side > 0),
                ("Г2", "обе стороны в сторону алгоритма", lambda x: x.side != 0),
                ("Г3", "конец покупок → шорт", lambda x: x.side > 0), ("Г3", "конец продаж → лонг", lambda x: x.side < 0),
                ("Г3", "обе стороны против алгоритма", lambda x: x.side != 0),
                ("Г3 I≥0,3%", "конец покупок → шорт", lambda x: x.side > 0),
                ("Г3 I≥0,3%", "конец продаж → лонг", lambda x: x.side < 0),
                ("Г3 I≥0,3%", "обе стороны против алгоритма", lambda x: x.side != 0)]
    for h in (4, 24):
        print(f"===== срок {h} ч =====")
        for hyp, name, f in variants:
            parts, cells, pos = [], [], 0
            for p in pers:
                x = X[p]
                x = x[(x.hyp == hyp) & f(x)].dropna(subset=[f"net{h}"])
                m, t, n = C.ct(x[f"net{h}"], x.t)
                mh, th, _ = C.ct(x[f"hed{h}"], x.t)
                mp, tp, _ = C.ct(x[f"net{h}"] - x[f"pl{h}"], x.t)
                ml, tl, _ = C.ct(x[f"net{h}"] - x[f"plL{h}"], x.t)
                mo = n / X[p].attrs["nd"] * USIZE[p] * 30.4 if n else 0
                cut = C.ts(C.PER[p][2])
                if np.isfinite(t) and t != 0:
                    parts.append((m, abs(m / t), n))
                pos += int(m > 0) if np.isfinite(m) else 0
                cells.append(f"  {p}: n={n} (~{mo:.0f}/мес на вселенную) {m:+.2%} (t {t:+.1f}), половины "
                             f"{x[x.t < cut][f'net{h}'].mean():+.2%} / {x[x.t >= cut][f'net{h}'].mean():+.2%} | "
                             f"с хеджем {mh:+.2%} (t {th:+.1f}) | сверх плацебо −7 сут {mp:+.2%} (t {tp:+.1f}), "
                             f"45/90/135 сут {ml:+.2%} (t {tl:+.1f}) | без стопа {x[f'nos{h}'].mean():+.2%} | "
                             f"стопов {x[f'stop{h}'].mean():.0%}")
            m, t = C.combine(parts)
            ok = (m >= 0.0015) and (t >= 1.5) and (pos >= 2)
            print(f"{hyp}, {name}: вместе {m:+.2%} (t {t:+.1f}), в плюсе {pos} из 3 → "
                  f"{'ПРОХОДИТ ОТБОР' if ok and h == 4 else ('проходит (запасной срок)' if ok else 'не проходит')}")
            print("\n".join(cells))
        print()


if __name__ == "__main__":
    report() if sys.argv[1] == "report" else run(sys.argv[1])
