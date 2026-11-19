"""s193 — эпизоды алгоритмов исполнения в ленте aggTrades: частоты по трём периодам, доля в обороте, длительность, сторона,
ритм, метки времени, связь с разлоками 🔑⁺, заводами 🐋 и входами журналов; полнота детектора на синтетических вставках.

Пороги эпизода записаны до просмотра (правило «гипотезы — до проверки»; доходы, цены после начала эпизода, сделки
и плацебо НЕ считаются; цена используется только до момента обнаружения — для описания):
- обнаружение (tape.eval_run): ≥ 20 частей, ≥ 30 мин, регулярность интервалов ≥ 0,5, чистота стороны ≥ 0,8;
- дубликаты D1/D1n и прогоны одного алгоритма с разными размерами (алгоритм по сумме $) сливаются: та же сторона,
  перекрытие по времени, сумма части ±30%;
- уровни: E1 — часть ≥ 100 $ и доля в обороте стороны от начала до обнаружения ≥ 1%; E3 — ≥ 3%; E10 — ≥ 10%;
  «крупный» — оборот эпизода к моменту обнаружения ≥ 50 тыс. $.
Частота «в месяц» — доля монето-суток SRS с эпизодом × медианный размер вселенной × 30,4."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

D = "/home/user/mc_data/s193"
DAY = 86400
USIZE = {"2020–2022": 121, "2022–2024": 177, "2024–2026": 268}
PERS = list(USIZE)
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)


def merge_runs(R):
    """Слить прогоны одного алгоритма: одни сутки, рынок, монета, сторона; пересечение по времени; сумма части ±30%."""
    R = R.sort_values(["mkt", "s", "d", "side", "t0"]).reset_index(drop=True)
    out = []
    for _, g in R.groupby(["mkt", "s", "d", "side"], sort=False):
        g = g.to_dict("records")
        used = [False] * len(g)
        for i in range(len(g)):
            if used[i]:
                continue
            grp = [i]
            used[i] = True
            changed = True
            while changed:
                changed = False
                for j in range(len(g)):
                    if used[j]:
                        continue
                    for k in grp:
                        a, b = g[k], g[j]
                        ov = min(a["t1"], b["t1"]) - max(a["t0"], b["t0"])
                        if ov > 0 and abs(np.log(a["vchild"] / b["vchild"])) <= np.log(1.3):
                            grp.append(j)
                            used[j] = True
                            changed = True
                            break
            rows = [g[k] for k in grp]
            # представитель — прогон по сумме (N), иначе крупнейший по обороту
            rep = max(rows, key=lambda z: (z["kind"] == "N", z["vtot"]))
            rep = dict(rep)
            rep["t0"] = min(z["t0"] for z in rows)
            rep["t1"] = max(z["t1"] for z in rows)
            rep["det_t"] = min(z["det_t"] for z in rows)
            rep["nmerged"] = len(rows)
            rep["kinds"] = "".join(sorted(set(z["kind"] for z in rows)))
            out.append(rep)
    return pd.DataFrame(out)


def per_month(n_events, n_days, per):
    return n_events / max(n_days, 1) * USIZE[per] * 30.4


def main():
    T = pd.read_pickle(f"{D}/tables.pkl")
    days, runs = T["days"], T["runs"]
    print(f"монето-суток: {len(days)} (ошибок/нет файла: {len(T['bad'])})")
    print(days.groupby(["per", "mkt"]).agg(n=("s", "size"), монет=("s", "nunique"),
                                           заявок_млн=("n_ord", lambda x: x.sum() / 1e6)).round(1).to_string())
    det = runs[runs.det_t.notna()].copy()
    print(f"\nобнаруженных прогонов (до слияния): {len(det)}")
    E = merge_runs(det)
    E["dur"] = (E.t1 - E.t0) / 60000
    E["lag"] = (E.det_t - E.t0) / 60000
    E["v_det"] = E.sh_det * 0          # заполняется ниже
    E["v_det"] = E.vchild * E.n_det
    E["E1"] = (E.vchild >= 100) & (E.sh_det >= 0.01)
    E["E3"] = (E.vchild >= 100) & (E.sh_det >= 0.03)
    E["E10"] = (E.vchild >= 100) & (E.sh_det >= 0.10)
    E["big"] = E.v_det >= 5e4
    E["srs"] = E.tags.str.contains("srs")
    E["hstart"] = ((E.t0 // 1000) % DAY) // 3600
    pd.to_pickle(E, f"{D}/episodes.pkl")
    print(f"эпизодов после слияния: {len(E)}; слито прогонов на эпизод: среднее {E.nmerged.mean():.2f}; "
          f"виды: {E.kinds.value_counts().to_dict()}")

    srs = days[days.tags.str.contains("srs") & (days.mkt == "um")]
    nd = srs.groupby("per").size()
    Es = E[E.srs & (E.mkt == "um")]
    print("\n== Частота эпизодов, фьючерсы, SRS (на монето-сутки; в месяц на вселенную ликвидных альтов) ==")
    for lvl in ("all", "E1", "E3", "E10", "big"):
        cells = []
        for per in PERS:
            x = Es[Es.per == per] if lvl == "all" else Es[(Es.per == per) & Es[lvl]]
            n = nd.get(per, 0)
            sell = (x.side < 0).sum()
            cells.append(f"{len(x) / max(n, 1):.3f} / {per_month(len(x), n, per):7.1f} мес (продаж {sell / max(len(x), 1):.0%},"
                         f" продаж в мес {per_month(sell, n, per):6.1f})")
        print(f"  {lvl:4s}: " + " | ".join(cells))
    print("  монето-суток SRS:", nd.to_dict(), " размер вселенной:", USIZE)

    print("\n== Описание эпизодов E1 (SRS, фьючерсы): медианы и квантили ==")
    x = Es[Es.E1]
    for per in PERS:
        y = x[x.per == per]
        if not len(y):
            continue
        q = lambda c: " / ".join(f"{v:,.3g}" for v in y[c].quantile([.1, .5, .9]))
        print(f"  {per}: n={len(y)}; длительность мин {q('dur')}; шаг с {q('med')}; часть $ {q('vchild')}; "
              f"оборот к обнаружению $ {q('v_det')}; доля стороны {q('sh_det')}; задержка обнаружения мин {q('lag')}")

    print("\n== Шаг (медианный интервал) обнаруженных эпизодов — частые значения (SRS, фьючерсы, все уровни) ==")
    st = Es.med.round(1)
    vc = st.value_counts().head(20)
    print("  " + ", ".join(f"{k:g} с: {v}" for k, v in vc.items()))
    for lvl in ("E1", "E3"):
        st = Es[Es[lvl]].med.round(1)
        print(f"  {lvl}: " + ", ".join(f"{k:g} с: {v}" for k, v in st.value_counts().head(15).items()))

    print("\n== Подпись встроенного TWAP Binance? Эпизоды с шагом 59,5–60,5 с: длительность ==")
    t60 = Es[(Es.med >= 59.5) & (Es.med <= 60.5)]
    durm = np.round((t60.t1 - t60.t0) / 60000 + 1)
    print(f"  эпизодов с шагом ≈ 60 с: {len(t60)} из {len(Es)}; у E1: {int(t60.E1.sum())}")
    print("  длительность (мин, частые):", durm.value_counts().head(15).to_dict())
    print("  длительность ≥ 1430 мин (≈ 24 ч, предел TWAP Binance):", int((durm >= 1430).sum()),
          "; у края суток (edge):", int(t60.edge.sum()))
    print("  секунда минуты: доля частей в модальной секунде, медиана:", round(float(t60.smode.median()), 3),
          "(у прочих", round(float(Es[~Es.index.isin(t60.index)].smode.median()), 3), ")")

    print("\n== Сторона, время суток начала, крупность (E1, SRS, фьючерсы) ==")
    for per in PERS:
        y = x[x.per == per]
        if not len(y):
            continue
        hh = y.groupby("hstart").size()
        print(f"  {per}: продаж {np.mean(y.side < 0):.0%}; часы начала (UTC, топ-5) {hh.sort_values(ascending=False).head(5).to_dict()};"
              f" монет {y.s.nunique()}; топ монет {y.s.value_counts().head(6).to_dict()}")

    # события: разлоки и заводы
    print("\n== Эпизоды на сутках событий против SRS того же периода (фьючерсы; доля монето-суток с эпизодом) ==")

    def rate(dd, ee, lvl):
        if not len(dd):
            return np.nan, 0
        keys = set(zip(dd.s, dd.d))
        hit = ee[ee[lvl]] if lvl != "all" else ee
        hit = set(zip(hit.s, hit.d)) & keys
        return len(hit) / len(keys), len(keys)

    for per in PERS:
        for lvl in ("E1", "E3"):
            out = []
            for name, cond in (("SRS", "srs"), ("разлок", "unlock"), ("завод", "whale"), ("контроль завода", "whale_ctl")):
                dd = days[(days.per == per) & (days.mkt == "um") & days.tags.str.contains(cond)]
                if cond == "whale":
                    dd = dd[~dd.tags.str.contains("whale_ctl") | dd.tags.str.contains("whale,") | (dd.tags == "whale")]
                ee = E[(E.per == per) & (E.mkt == "um")]
                r, n = rate(dd, ee, lvl)
                out.append(f"{name} {r:.1%} (n={n})")
            print(f"  {per} {lvl}: " + "; ".join(out))
    print("  спот:")
    for per in PERS:
        out = []
        for name, cond in (("завод", "whale"), ("контроль", "whale_ctl")):
            dd = days[(days.per == per) & (days.mkt == "spot") & days.tags.str.contains(cond)]
            if cond == "whale":
                dd = dd[[("whale" in t.split(",")) for t in dd.tags]]
            ee = E[(E.per == per) & (E.mkt == "spot")]
            r1, n = rate(dd, ee, "E1")
            r3, _ = rate(dd, ee, "E3")
            ee_s = ee[ee.side < 0]
            r1s, _ = rate(dd, ee_s, "E1")
            out.append(f"{name}: E1 {r1:.1%}, E3 {r3:.1%}, E1-продажи {r1s:.1%} (n={n})")
        print(f"  {per} " + "; ".join(out))

    # журналы: эпизод E1 на той же монете в те же сутки до входа журнала
    print("\n== Журналы: эпизод E1 той же монеты в те же сутки до входа (SRS-сутки, фьючерсы) ==")
    for per in PERS:
        Jr = C.journals(per)
        Jr["d"] = (Jr.t // DAY) * DAY
        sd = srs[srs.per == per][["s", "d"]]
        m = Jr.merge(sd, on=["s", "d"])
        if not len(m):
            continue
        e1 = Es[(Es.per == per) & Es.E1]
        hits = []
        for r in m.itertuples():
            z = e1[(e1.s == r.s) & (e1.d == r.d) & (e1.det_t / 1000 < r.t)]
            hits.append((len(z) > 0, (z.side < 0).any(), (z.side > 0).any()))
        h = np.array(hits)
        # база: доля SRS-суток с эпизодом E1, обнаруженным до того же часа суток
        sec = (m.t % DAY).values
        base = []
        for tod in sec:
            base.append(np.mean([0]))
        e1d = e1.groupby(["s", "d"]).det_t.min() / 1000 % DAY
        allk = list(zip(sd.s, sd.d))
        tod_det = np.array([e1d.get(k, np.inf) for k in allk])
        base = np.mean([np.mean(tod_det < t) for t in sec])
        by = m.assign(hit=h[:, 0]).groupby("j").hit.agg(["mean", "size"])
        print(f"  {per}: входов на SRS-сутках {len(m)}; эпизод E1 до входа {h[:, 0].mean():.1%} (продажа {h[:, 1].mean():.1%},"
              f" покупка {h[:, 2].mean():.1%}); база SRS к тому же часу {base:.1%}; по журналам "
              + ", ".join(f"{j} {v['mean']:.0%} ({int(v['size'])})" for j, v in by.iterrows()))

    # цена до обнаружения (описание): ход от открытия суток до обнаружения
    print("\n== Цена до обнаружения (описание): ход от открытия суток до цены в момент обнаружения, E1, SRS ==")
    for per in PERS:
        y = x[x.per == per].merge(srs[["s", "d", "p_open"]], on=["s", "d"])
        if not len(y):
            continue
        r0 = y.p_det / y.p_open - 1
        print(f"  {per}: продажи — медиана {np.median(r0[y.side < 0]):+.2%}, покупки — {np.median(r0[y.side > 0]):+.2%};"
              f" |ход| > 5% у {np.mean(np.abs(r0) > 0.05):.0%}")


if __name__ == "__main__":
    main()
