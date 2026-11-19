"""s186 — размер потока ребаланса Gate по монетам и времени (2020–2026): множитель M = Σ L(L−1)·NAV, NAV ≈ оборот
токена / K; доля потока в обороте перпа Binance и Gate на событиях «ход за 24 ч до 16:00 UTC ≥ 10%»; вклад обратных
и 5x-токенов; режимы правил Gate (цель 2,3 до 01.04.2025, полосы с 17.07.2025) и пороги внутридневного ребаланса
по режимам. Калибровка K: Gate 16.09.2021 — NAV > $100 млн (пресс-релиз), выжившие пары торговали $38 млн в сутки
(09.09–23.09.2021), в 01.2025 выжившие — $81 млн в сутки при общем обороте $216 млн (6,7 млрд за январь) → покрытие ~38%,
оборот ≈ NAV → K ≈ 1; в расчётах K = 1 и K = 2 (поток ∝ 1/K).
Лог — gate_flow.log. Доходы не считаются."""
import pickle

import numpy as np
import pandas as pd

import common186 as C

L = C.Log("gate_flow")
T_SW = C.ts("2025-04-01") + 16 * 3600
T_BAND = C.ts("2025-07-17") + 16 * 3600


def main():
    U = pickle.load(open(f"{C.OUT}/lt_universe.pkl", "rb"))
    G = U["G"]
    gd = pickle.load(open(f"{C.OUT}/gate_daily.pkl", "rb"))
    gp = pickle.load(open(f"{C.OUT}/gate_perp_daily.pkl", "rb"))
    lev = dict(zip(G.pair, G.lev))
    und = dict(zip(G.pair, G.und))
    # M по монете и суткам (K = 1), раздельно: 3L, 3S, 5L, 5S
    parts = {}
    for pair, df in gd.items():
        if pair not in lev:
            continue
        L0 = float(lev[pair])
        Le = np.where((abs(L0) == 3) & (df.index.values < T_SW), np.sign(L0) * 2.3, L0)
        m = pd.Series(Le * (Le - 1), index=df.index) * df.qv.rolling(7, min_periods=1).mean().shift(1)
        key = f"{abs(int(L0))}{'L' if L0 > 0 else 'S'}"
        parts.setdefault(und[pair], {}).setdefault(key, []).append(m)
    M = {u: {k: pd.concat(v, axis=1).sum(axis=1) for k, v in d.items()} for u, d in parts.items()}
    for per in C.PERS:
        X = pickle.load(open(f"{C.OUT}/cd_{per}.pkl", "rb"))["cd"]
        e = X[(X.H == 16)].copy()
        e["b"] = e.b.astype(str)
        e = e[e.b.isin(M.keys())]
        gu = U["U"][U["U"].ex == "gate"]
        first = gu.groupby("und").t0.min().to_dict()                  # первый день торгов любого токена монеты
        e = e[[(e_t + 16 * 3600) >= first.get(b, 9e9) for b, e_t in zip(e.b, e.D)]]
        cols = {}
        for k in ("3L", "3S", "5L", "5S"):
            cols[k] = np.array([M[b][k].get(D, np.nan) if k in M[b] else 0.0 for b, D in zip(e.b, e.D)])
        e["M"] = np.nansum(np.vstack([cols[k] for k in cols]), axis=0)
        e.loc[e.M <= 0, "M"] = np.nan
        for k in cols:
            e["M" + k] = cols[k]
        gv = np.full(len(e), np.nan)
        for i, (b, D) in enumerate(zip(e.b, e.D)):
            df = gp.get(b)
            if df is not None and len(df):
                w = df.qv[(df.index >= D - 7 * C.DAY) & (df.index < D)]
                if len(w):
                    gv[i] = w.mean()
        e["gv"] = gv
        mo = C.C3.months(per)
        L(f"\n===== {per}: монето-суток с токенами Gate и оценкой M: {e.M.notna().sum()}")
        up = e[(e.r24 >= 0.10) & e.M.notna()]
        for K in (1.0, 2.0):
            fb = up.M * up.r24 / K / up.v7
            fg = up.M * up.r24 / K / up.gv
            L(f"  K={K:g}, r24 ≥ 10% ({len(up) / mo:.1f} в мес.): поток / сут. оборот перпа Binance — медиана "
              f"{np.nanmedian(fb) * 100:.2f}%, p90 {np.nanpercentile(fb, 90) * 100:.2f}%; ≥ 0,3%: {np.nansum(fb >= 0.003) / mo:.1f} "
              f"в мес.; ≥ 1%: {np.nansum(fb >= 0.01) / mo:.1f} в мес. | к перпу Gate — медиана {np.nanmedian(fg) * 100:.1f}%, "
              f"p90 {np.nanpercentile(fg, 90) * 100:.1f}%")
        sh = {k: np.nansum(up["M" + k]) / np.nansum(up.M) for k in ("3L", "3S", "5L", "5S")}
        L("  доля в M по типам токенов (события r24 ≥ 10%): " + ", ".join(f"{k} {v * 100:.0f}%" for k, v in sh.items()))
        top = up.groupby("b").apply(lambda x: np.nanmedian(x.M * x.r24 / x.v7)).sort_values(ascending=False).head(12)
        L("  монеты с наибольшей медианной долей потока (K=1) к обороту Binance: " +
          ", ".join(f"{b} {v * 100:.2f}%" for b, v in top.items()))
        # по полугодиям — рост продукта
        hy = pd.to_datetime(up.D, unit="s").dt.to_period("Q")
        q = up.assign(f=up.M * up.r24 / up.v7, q=hy).groupby("q").agg(n=("f", "size"), med=("f", "median"))
        L("  по кварталам (K=1): " + "; ".join(f"{i} n={r.n} медиана {r.med * 100:.2f}%" for i, r in q.iterrows()))
        # пороги внутридневного ребаланса по режимам правил Gate (покупка обратными токенами на росте от цены 16:00)
        if per == "2024–2026":
            for name, a, b, col in (("до 01.04.2025, 3S при +7,6% (нижняя граница — пересечение +10%)", 0, T_SW, "up_10"),
                                    ("до 01.04.2025, 3S при +7,6% (верхняя граница — пересечение +6,67%)", 0, T_SW, "up_6_67"),
                                    ("до 01.04.2025, 3L при +20% (ход ±20%)", 0, T_SW, "up_20"),
                                    ("01.04–17.07.2025, 3S при +6,67%", T_SW, T_BAND, "up_6_67"),
                                    ("с 17.07.2025, 3S при +12%", T_BAND, 2e9, "up_12"),
                                    ("с 17.07.2025, 3L при +20%", T_BAND, 2e9, "up_20")):
                x = e[(e.D + 16 * 3600 >= a) & (e.D + 16 * 3600 < b)]
                m_ = (min(b, C.ts(C.PER[per]["t1"])) - max(a, C.ts(C.PER[per]["t0"]))) / (30.4 * C.DAY)
                L(f"  порог {name}: {(x[col] >= 0).sum() / m_:.1f} в мес. (монет с токенами в среднем "
                  f"{x.groupby('D').size().mean():.0f})")


if __name__ == "__main__":
    main()
