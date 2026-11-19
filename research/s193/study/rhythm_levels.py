"""s193 — D2 «ритм» (периодограмма по часам и сторонам) и D3 «потолок/пол» (заменитель айсберга): частоты по периодам,
частые периоды, односторонность, пересечение с эпизодами D1/D1n; полнота детекторов на синтетических вставках.
Доходы не считаются."""
import numpy as np
import pandas as pd

D = "/home/user/mc_data/s193"
PERS = ["2020–2022", "2022–2024", "2024–2026"]
USIZE = {"2020–2022": 121, "2022–2024": 177, "2024–2026": 268}


def main():
    T = pd.read_pickle(f"{D}/tables.pkl")
    days, d2, lev, inj = T["days"], T["d2"], T["lev"], T["inj"]
    E = pd.read_pickle(f"{D}/episodes.pkl")
    srs = days[days.tags.str.contains("srs") & (days.mkt == "um")]
    nd = srs.groupby("per").size()
    x = d2[d2.tags.str.contains("srs") & (d2.mkt == "um")].copy()
    # белый шум: SNR ~ Exp(1)/ln2, максимум по ~1790 частотам — около 11,6; порог 50 — p ≈ 1790·2^-50
    print("== D2: часы с ритмом (SNR ≥ 50), фьючерсы SRS ==")
    for per in PERS:
        y = x[x.per == per]
        n = nd.get(per, 1)
        a = y[y.snr >= 50]
        one = a[a.snr_oth < 5]
        print(f"  {per}: часов с SNR ≥ 50 — {len(a) / n:.2f} на монето-сутки (односторонних {len(one) / n:.2f}); "
              f"монето-суток с ритмом {a.groupby(['s', 'd']).ngroups / n:.1%}; SNR ≥ 200 — {np.mean(y.snr >= 200) * len(y) / n:.2f}")
        pc = np.round(one.period, 1).value_counts().head(12)
        print("    частые периоды односторонних (с):", ", ".join(f"{k:g}: {v}" for k, v in pc.items()))
    # пересечение D2 с эпизодами D1/D1n
    print("\n== D2 ∩ D1/D1n: односторонний ритм в часе, где у той же монеты и стороны идёт обнаруженный эпизод ==")
    Es = E[E.srs & (E.mkt == "um")]
    for per in PERS:
        y = x[(x.per == per) & (x.snr >= 50) & (x.snr_oth < 5)]
        e = Es[Es.per == per]
        hit = 0
        for r in y.itertuples():
            h0 = r.d * 1000 + r.h * 3_600_000
            z = e[(e.s == r.s) & (e.d == r.d) & (e.side == r.side) & (e.t0 < h0 + 3_600_000) & (e.t1 > h0)]
            hit += len(z) > 0
        print(f"  {per}: односторонних часов {len(y)}, из них при эпизоде D1/D1n {hit / max(len(y), 1):.0%} — "
              f"остальное ритм без одинаковых размеров или сумм")
    # D3
    print("\n== D3: потолок/пол (≥ 3 касания, уровень не пробит ≥ 30 мин), фьючерсы SRS ==")
    L = lev[lev.tags.str.contains("srs") & (lev.mkt == "um")].copy()
    L["sh"] = L.vlev / L.vtot
    for per in PERS:
        y = L[L.per == per]
        n = nd.get(per, 1)
        ok = y[(y.rng_ticks >= 20)]
        big = ok[ok.sh >= 0.05]
        print(f"  {per}: всех {len(y) / n:.2f} на монето-сутки; при размахе блока ≥ 20 шагов цены {len(ok) / n:.2f};"
              f" из них объём на уровне ≥ 5% оборота до обнаружения {len(big) / n:.3f} "
              f"(в месяц на вселенную {len(big) / n * USIZE[per] * 30.4:.0f}); потолков {np.mean(big.kind == 'ceil'):.0%}")
    # полнота
    print("\n== Полнота на синтетических TWAP (вставки в 10% SRS-суток) ==")
    I = inj.copy()
    I["d2_25"] = I.p_snr >= 25
    I["d2_50"] = I.p_snr >= 50
    I["any"] = (I.q_det == 1) | (I.n_det == 1) | I.d2_50
    print(f"  вставок {len(I)}")
    g = I.groupby(["mode", "jit"])[["q_det", "n_det", "d2_50", "any"]].mean()
    print(g.round(2).to_string())
    for mode in ("exact", "rand10"):
        for jit in (0.0, 0.2):
            y = I[(I["mode"] == mode) & (I.jit == jit)]
            t = y.pivot_table(index="Y", columns="P", values="any", aggfunc="mean")
            print(f"\n  размер {mode}, разброс шага ±{jit:.0%}: доля найденных (любым детектором), строки — доля в обороте "
                  f"стороны, столбцы — шаг, с")
            print(t.round(2).to_string())
    y = I[(I["mode"] == "exact") & (I.q_det == 1)]
    print(f"\n  задержка обнаружения D1 (мин): медиана {y.q_lag.median():.1f}, p90 {y.q_lag.quantile(.9):.1f}")
    print("  по периодам (любой детектор):", I.groupby("per")["any"].mean().round(2).to_dict())


if __name__ == "__main__":
    main()
