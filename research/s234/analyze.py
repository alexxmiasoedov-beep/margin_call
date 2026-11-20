"""s234 — где теряют журналы: путь цены сделок после входа (MAE/MFE) и другие стопы на тех же сделках.
Для журналов с плечом ×10 и стопом: перебор стопа при тех же тейке и сроке по 5-мин свечам (high/low цены сделок;
бот считает стоп по марк-цене — приближение). Шорт: доход = −(выход/вход − 1) − 0,1% комиссии; фандинг не учитывается
в симуляции (в итогах журнала он есть).
Запуск из /home/user/mc_data: python3 <repo>/research/s234/analyze.py"""
import pickle

import numpy as np
import pandas as pd

HOLD = {"🏦": 170, "🏦³": 170, "🌊": 2}
FEE = 0.001


def sim(a, t, px, side, tp, sl, hold_h):
    """Сделка по 5-мин свечам от входа: тейк tp% и стоп sl% (None — нет), выход по времени. → (доход, исход, MAE%, MFE%)."""
    m = (a[:, 0] + 300 > t) & (a[:, 0] < t + hold_h * 3600)
    b = a[m]
    if not len(b):
        return np.nan, "нет", np.nan, np.nan
    sgn = -1 if side == "short" else 1
    adv = (b[:, 1] / px - 1) * 100 if side == "short" else (1 - b[:, 2] / px) * 100     # против позиции, %
    fav = (1 - b[:, 2] / px) * 100 if side == "short" else (b[:, 1] / px - 1) * 100     # в пользу, %
    for i in range(len(b)):
        hit_sl = sl is not None and adv[i] >= sl
        hit_tp = tp is not None and fav[i] >= tp
        if hit_sl:                                   # в одной свече со стопом и тейком — считаем стоп (осторожно)
            return -sl / 100 - FEE, "стоп", adv[:i + 1].max(), fav[:i + 1].max()
        if hit_tp:
            return tp / 100 - FEE, "тейк", adv[:i + 1].max(), fav[:i + 1].max()
    r = sgn * (b[-1, 3] / px - 1) - FEE
    return r, "время", adv.max(), fav.max()


def main():
    D = pd.read_pickle("s234/trades_1711.pkl"); P = pickle.load(open("s234/paths.pkl", "rb"))
    D = D[D.pnl.notna() & (D.lev == 10)].copy()
    rows = []
    for r in D.itertuples():
        a = P.get((r.j, r.t, r.s))
        if a is None:
            continue
        hold = 48
        base = sim(a, r.t, r.px, r.side, r.tp, r.sl, hold)
        nost = sim(a, r.t, r.px, r.side, r.tp, None, hold)
        rec = {"j": r.j, "t": r.t, "s": r.s, "why": r.why, "ret": r.ret, "sim": base[0], "sim_why": base[1],
               "mae": base[2], "mfe": base[3], "nost": nost[0], "nost_why": nost[1], "mae_full": nost[2]}
        for sl in (8, 10, 12, 15, 20, 25, 30, 40):
            rec[f"sl{sl}"] = sim(a, r.t, r.px, r.side, r.tp, sl, hold)[0]
        for hh in (4, 12, 24):
            rec[f"h{hh}"] = sim(a, r.t, r.px, r.side, r.tp, r.sl, hh)[0]
        rows.append(rec)
    R = pd.DataFrame(rows)
    R.to_pickle("s234/sim.pkl")
    ok = R.sim_why == R.why
    print(f"сделок ×10: {len(R)}; исход симуляции совпал с журналом у {ok.mean():.0%}; доход журнала {R.ret.mean():+.2%}, "
          f"симуляции {R.sim.mean():+.2%}")
    print("\nMAE (худший ход против позиции до выхода) у сделок, закрытых по тейку и по времени, — доля сделок:")
    W = R[R.why != "стоп"]
    for x in (5, 8, 10, 12, 15, 20):
        print(f"  ≥ {x:>2}%: {(W.mae >= x).mean():.0%}")
    S = R[R.why == "стоп"]
    print(f"\nстопов {len(S)}; без стопа (тот же тейк и срок) они дали бы {S.nost.mean():+.2%} в среднем; вернулись к тейку "
          f"{(S.nost_why == 'тейк').mean():.0%}; худший ход без стопа — медиана {S.mae_full.median():.0f}%, "
          f"доля ≥ 50%: {(S.mae_full >= 50).mean():.0%}")
    cols = ["sl8", "sl10", "sl12", "sl15", "sl20", "sl25", "sl30", "sl40", "nost", "h4", "h12", "h24", "sim"]
    print("\nсредний доход на сделку при другом стопе (тот же тейк, срок 48 ч) и при коротком сроке со своим стопом:")
    T = R.groupby("j")[cols].mean().mul(100).round(2)
    T.insert(0, "n", R.groupby("j").size())
    T.columns = ["n", "стоп 8", "10", "12", "15", "20", "25", "30", "40", "без стопа", "срок 4 ч", "12 ч", "24 ч", "как в журнале"]
    print(T.sort_values("n", ascending=False).to_string())
    print("\nвсе журналы:", R[cols].mean().mul(100).round(2).to_dict())


if __name__ == "__main__":
    main()
