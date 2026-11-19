"""s193 — дневные признаки ленты по периодам (фьючерсы SRS и спот): память знака (Lillo–Mike–Farmer), серии одной
стороны, Бенфорд и круглые размеры (Cong и др. 2023), парные заявки («мытьё», s14), метки времени (секунда минуты,
50-мс доля секунды). Проверка согласия γ = α − 1: хвост распределения оборота обнаруженных эпизодов (оценка Хилла).
Связь дневных признаков с эпизодами E3 (сутки с эпизодом против без). Доходы не считаются."""
import numpy as np
import pandas as pd

D = "/home/user/mc_data/s193"
PERS = ["2020–2022", "2022–2024", "2024–2026"]


def hill(x, k):
    x = np.sort(np.asarray(x, float))[::-1]
    x = x[x > 0]
    if len(x) <= k + 1:
        return np.nan
    return 1.0 / np.mean(np.log(x[:k] / x[k]))


def main():
    T = pd.read_pickle(f"{D}/tables.pkl")
    days = T["days"]
    E = pd.read_pickle(f"{D}/episodes.pkl")
    cols = ["gamma", "acf1", "acf10", "acf100", "acf1000", "p_stay", "rl_max", "mad_q", "mad_v", "round_q", "round_v",
            "pair_n", "pair_v", "sec_max", "sec0", "sec_kl", "ms0", "ms_kl", "lev_mean"]
    for mkt in ("um", "spot"):
        x = days[(days.mkt == mkt) & (days.tags.str.contains("srs") if mkt == "um" else days.tags.str.contains("whale"))]
        print(f"\n== {('фьючерсы, SRS' if mkt == 'um' else 'спот, сутки заводов и контроля')}: медианы (p10 / p90) ==")
        for c in cols:
            cells = []
            for per in PERS:
                y = x[x.per == per][c].dropna()
                if len(y):
                    cells.append(f"{y.median():.4g} ({y.quantile(.1):.3g} / {y.quantile(.9):.3g})")
                else:
                    cells.append("—")
            print(f"  {c:9s}: " + " | ".join(cells))
    um = days[(days.mkt == "um") & days.tags.str.contains("srs")].copy()
    # равномерная секунда минуты — 1/60 = 0,0167; ms0 равномерно — 0,05
    print("\n== Метки времени: сутки, где на одну секунду минуты приходится ≥ 5% заявок; на первые 50 мс секунды ≥ 10% ==")
    for per in PERS:
        y = um[um.per == per]
        print(f"  {per}: sec_max ≥ 0,05 — {np.mean(y.sec_max >= 0.05):.1%}; sec0 (секунда :00) медиана {y.sec0.median():.4f};"
              f" ms0 ≥ 0,10 — {np.mean(y.ms0 >= 0.10):.1%}")
    print("\n== Бенфорд (MAD первых цифр размера, порог несоответствия Nigrini 0,015) ==")
    for per in PERS:
        y = um[um.per == per]
        print(f"  {per}: размер в монетах MAD > 0,015 — {np.mean(y.mad_q > 0.015):.1%}; сумма $ — {np.mean(y.mad_v > 0.015):.1%}")
    print("\n== Парные заявки (покупка и продажа одного размера за ≤ 2 с): доля заявок ==")
    for per in PERS:
        y = um[um.per == per]
        print(f"  {per}: медиана {y.pair_n.median():.3%}; p90 {y.pair_n.quantile(.9):.2%}; сутки с ≥ 10% — "
              f"{np.mean(y.pair_n >= 0.10):.1%}; по обороту медиана {y.pair_v.median():.3%}")
        top = y.sort_values("pair_n", ascending=False).head(5)
        print("    крайние:", ", ".join(f"{r.s} {pd.Timestamp(r.d, unit='s').date()} {r.pair_n:.0%}" for r in top.itertuples()))
    # γ и хвост эпизодов
    print("\n== Память знака: γ по суткам и хвост оборота эпизодов (γ = α − 1 у Lillo–Mike–Farmer) ==")
    Es = E[E.srs & (E.mkt == "um")]
    for per in PERS:
        y = um[um.per == per]
        g = y.gamma.dropna()
        z = Es[Es.per == per].merge(y[["s", "d", "vol"]], on=["s", "d"])
        q = (z.vtot / z.vol).values
        a = [hill(q, k) for k in (50, 100, 200)]
        print(f"  {per}: γ медиана {g.median():.3f} (p25 {g.quantile(.25):.3f}, p75 {g.quantile(.75):.3f}); acf100 медиана "
              f"{y.acf100.median():.3f}; эпизодов {len(z)}; α Хилла (k=50/100/200) по обороту эпизода к суточному: "
              + " / ".join(f"{v:.2f}" for v in a) + f" → α − 1 = {np.nanmean(a) - 1:.2f}")
    # сутки с эпизодом E3 против без
    print("\n== Сутки с эпизодом E3 (продажа / покупка) против без: медианы признаков ==")
    for per in PERS:
        y = um[um.per == per].copy()
        e3 = Es[(Es.per == per) & Es.E3]
        ks = set(zip(e3[e3.side < 0].s, e3[e3.side < 0].d))
        kb = set(zip(e3[e3.side > 0].s, e3[e3.side > 0].d))
        y["es"] = [(s, d) in ks for s, d in zip(y.s, y.d)]
        y["eb"] = [(s, d) in kb for s, d in zip(y.s, y.d)]
        out = []
        for c in ("acf10", "acf100", "p_stay", "pair_n", "sec_max", "mad_q", "vol"):
            out.append(f"{c} {y[y.es][c].median():.3g}/{y[y.eb][c].median():.3g}/{y[~y.es & ~y.eb][c].median():.3g}")
        print(f"  {per} (n={int(y.es.sum())}/{int(y.eb.sum())}/{int((~y.es & ~y.eb).sum())}): " + "; ".join(out))


if __name__ == "__main__":
    main()
