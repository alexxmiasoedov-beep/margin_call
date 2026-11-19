"""s193 — подпись таймера по времени: эпизоды с шагом 59,5–60,5 с и ≥ 50% частей в одной секунде минуты (SRS, фьючерсы)
по полугодиям на монето-сутки; длительности «таймеров» (кратность часу, 8 ч, 24 ч); сравнение с датами запуска TWAP Binance
(сайт и приложение — 01.11.2021, API — 27.04.2022). Только описание."""
import numpy as np
import pandas as pd

D = "/home/user/mc_data/s193"


def main():
    T = pd.read_pickle(f"{D}/tables.pkl")
    days = T["days"]
    E = pd.read_pickle(f"{D}/episodes.pkl")
    srs = days[days.tags.str.contains("srs") & (days.mkt == "um")].copy()
    Es = E[E.srs & (E.mkt == "um")].copy()
    Es["timer"] = (Es.med >= 59.5) & (Es.med <= 60.5) & (Es.smode >= 0.5)
    for X in (srs, Es):
        dt = pd.to_datetime(X.d, unit="s")
        X["half"] = dt.dt.year.astype(str) + np.where(dt.dt.month <= 6, "-H1", "-H2")
    nd = srs.groupby("half").size()
    g = Es.groupby("half").agg(timer=("timer", "sum"), allep=("timer", "size"))
    g1 = Es[Es.E1].groupby("half").agg(timer_E1=("timer", "sum"))
    out = pd.concat([nd.rename("сутки"), g, g1], axis=1).fillna(0)
    out["таймер на 100 суток"] = 100 * out.timer / out["сутки"]
    out["таймер E1 на 100 суток"] = 100 * out.timer_E1 / out["сутки"]
    out["доля таймера"] = out.timer / out.allep
    print("== Эпизоды «таймер 60 с» по полугодиям (SRS, фьючерсы) ==")
    print(out.round(3).to_string())
    first = Es[Es.timer].sort_values("d").head(5)
    print("\nпервые эпизоды таймера в выборке:", ", ".join(f"{r.s} {pd.Timestamp(r.d, unit='s').date()}" for r in first.itertuples()))
    tm = E[(E.med >= 59.5) & (E.med <= 60.5) & (E.smode >= 0.5) & (E.edge == 0)]
    durm = np.round((tm.t1 - tm.t0) / 60000 + 1)
    print(f"\nдлительность таймеров вне края суток (мин, частые; всего {len(tm)}):", durm.value_counts().head(12).to_dict())
    print("кратные 60 мин (±1):", int(np.sum(np.abs(durm - 60 * np.round(durm / 60)) <= 1)), "из", len(durm))


if __name__ == "__main__":
    main()
