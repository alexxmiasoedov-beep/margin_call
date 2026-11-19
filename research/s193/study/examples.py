"""s193 — примеры найденных отпечатков (монета, сутки, время UTC): крупнейшие эпизоды E3 по обороту на каждый период
(фьючерсы и спот), эпизоды «таймера» (шаг 60 с, одна секунда минуты), суточные TWAP, крайние сутки по парным заявкам и
по ритму D2. Только описание ленты; цены после обнаружения не читаются."""
import numpy as np
import pandas as pd

D = "/home/user/mc_data/s193"
PERS = ["2020–2022", "2022–2024", "2024–2026"]


def hm(ms):
    return pd.Timestamp(int(ms), unit="ms").strftime("%H:%M")


def main():
    E = pd.read_pickle(f"{D}/episodes.pkl")
    T = pd.read_pickle(f"{D}/tables.pkl")
    pd.set_option("display.width", 250)
    for per in PERS:
        for mkt in ("um", "spot"):
            x = E[(E.per == per) & (E.mkt == mkt) & E.E3].sort_values("vtot", ascending=False).head(8)
            if not len(x):
                continue
            print(f"\n== {per} {mkt}: крупнейшие эпизоды E3 по обороту ==")
            for r in x.itertuples():
                print(f"  {r.s} {pd.Timestamp(r.d, unit='s').date()} {hm(r.t0)}–{hm(r.t1)} UTC "
                      f"{'продажа' if r.side < 0 else 'покупка'}: {r.n} частей, шаг {r.med:.2f} с, часть ${r.vchild:,.0f}"
                      f" ({'размер' if r.kind == 'Q' else 'сумма'} {r.key:g}), всего ${r.vtot:,.0f}, доля стороны "
                      f"{r.sh_side:.1%}, длительность {r.dur:.0f} мин, секунда минуты {r.smode:.0%}, теги {r.tags}")
    print("\n== Таймер: шаг 59,5–60,5 с, ≥ 50% частей в одной секунде минуты, крупнейшие по обороту ==")
    x = E[(E.med >= 59.5) & (E.med <= 60.5) & (E.smode >= 0.5)].sort_values("vtot", ascending=False).head(10)
    for r in x.itertuples():
        print(f"  {r.per} {r.mkt} {r.s} {pd.Timestamp(r.d, unit='s').date()} {hm(r.t0)}–{hm(r.t1)} "
              f"{'продажа' if r.side < 0 else 'покупка'}: {r.n} частей по ${r.vchild:,.0f}, всего ${r.vtot:,.0f}, "
              f"доля {r.sh_side:.1%}, секунда минуты {r.smode:.0%}")
    print("\n== Почти суточные эпизоды (≥ 20 ч) ==")
    x = E[E.dur >= 1200].sort_values("vtot", ascending=False).head(10)
    for r in x.itertuples():
        print(f"  {r.per} {r.mkt} {r.s} {pd.Timestamp(r.d, unit='s').date()} {hm(r.t0)}–{hm(r.t1)} "
              f"{'продажа' if r.side < 0 else 'покупка'}: {r.n} частей, шаг {r.med:.2f} с, часть ${r.vchild:,.0f}, "
              f"всего ${r.vtot:,.0f}, доля {r.sh_side:.1%}")
    print("\n== Ритм D2: крупнейший SNR (односторонний) ==")
    d2 = T["d2"]
    x = d2[(d2.snr_oth < 5) & (d2.period <= 200)].sort_values("snr", ascending=False).head(10)
    for r in x.itertuples():
        print(f"  {r.per} {r.mkt} {r.s} {pd.Timestamp(r.d, unit='s').date()} час {r.h:02d} UTC "
              f"{'продажа' if r.side < 0 else 'покупка'}: период {r.period:.2f} с, SNR {r.snr:.0f}")
    print("\n== Сутки с наибольшей долей парных заявок (одинаковый размер, разные стороны, ≤ 2 с) ==")
    dd = T["days"]
    x = dd.sort_values("pair_n", ascending=False).head(10)
    for r in x.itertuples():
        print(f"  {r.per} {r.mkt} {r.s} {pd.Timestamp(r.d, unit='s').date()}: пар {r.pair_n:.0%} заявок, "
              f"{r.pair_v:.1%} оборота")


if __name__ == "__main__":
    main()
