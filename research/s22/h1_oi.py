"""Г1 (д): перповый аналог вынужденного закрытия шортов — цена фьючерса за 4 ч +5% и больше, а открытый интерес за те же
4 ч упал (шорты выкупают). События — s22/oi_events.pkl (oi_fetch.py: все 869 фьючерсов, одно на монету за сутки).
OI — в монетах, 5-мин метрики data.binance.vision. В s9 шорт после пампа с падением OI на 48 ч давал −3…−6% на сделку;
здесь — 48 ч против 7 суток. Ячейки: OI упал / вырос; крайние: ≤ −5% и ≥ +20%; монеты в канале MarginData в час T и вне.
Исход — доход шорта к рынку, сделки со стопом 50% (цена + фандинг + комиссия); t — с кластеризацией по дню. Запуск из
папки с данными."""
import sys
import numpy as np, pandas as pd

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import H, ct, fwd, oi_at, summ
from borrow_trades import sims

if __name__ == "__main__":
    E = pd.read_pickle("s22/oi_events.pkl").reset_index(drop=True)
    E["oi1"] = [oi_at(s, T) for s, T in zip(E.s, E["T"])]
    E["oi0"] = [oi_at(s, T - 4 * H) for s, T in zip(E.s, E["T"])]
    E["doi"] = E.oi1 / E.oi0 - 1
    P = pd.read_pickle("s21/panel.pkl")[["s", "T"]]
    inch = set(zip(P.s, P["T"]))
    E["ch"] = [(s, T) in inch for s, T in zip(E.s, E["T"])]
    E = E[np.isfinite(E.doi)].reset_index(drop=True)
    print(f"событий с OI: {len(E)} (в канале {E.ch.sum()}); OI за 4 ч: медиана {E.doi.median() * 100:+.1f}%, упал у {(E.doi < 0).mean():.0%}")
    for h in (48, 168, 336, 720):
        E[f"x{h}"] = [fwd(s, T, h) for s, T in zip(E.s, E["T"])]
    E.to_pickle("s22/h1_oi.pkl")
    for nm, m in (("все события", E.doi == E.doi), ("OI упал", E.doi < 0), ("OI вырос", E.doi >= 0),
                  ("OI упал на 5%+", E.doi <= -0.05), ("OI вырос на 20%+", E.doi >= 0.20),
                  ("OI упал, монета в канале", (E.doi < 0) & E.ch), ("OI упал, монеты в канале нет", (E.doi < 0) & ~E.ch),
                  ("OI вырос, монета в канале", (E.doi >= 0) & E.ch)):
        d = E[m]
        print(f"\n{nm}: {len(d)}")
        print("  шорт к рынку: " + " | ".join(f"{h // 24} сут {np.nanmean(d[f'x{h}']) * 100:+.2f}% (t {ct(d[f'x{h}'].values, d['T'].values)[1]:+.1f})"
                                             for h in (48, 168, 336, 720)))
        for hold in (48, 168):
            R = sims(d, sl=0.5, hold_h=hold)
            if len(R):
                print(f"  сделки {hold} ч, стоп 50%: {summ(R.net.values, R['T'].values)}; цена {R.price.mean() * 100:+.2f}%, "
                      f"фандинг шорту {R.fund.mean() * 100:+.2f}%")
