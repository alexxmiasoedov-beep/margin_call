"""s188 — пробы частот по нашим данным (без доходов, сделок и плацебо — правило «гипотезы — до проверки»).

1. «Пробой волатильности» на Upbit (логика ботов jocoding/pyupbit-autotrade и книги wikidocs 1665, Larry Williams):
   цель дня = открытие + k·(максимум − минимум прошлого дня), k = 0,5; бот покупает при пробое цели и продаёт всё за
   10 с до конца суток Upbit (08:59:50 KST = 23:59:50 UTC). Сутки Upbit начинаются в 00:00 UTC, поэтому берутся
   суточные свечи перпа Binance UTC (дневные панели s183) как приближение цены Upbit. Считается: сколько монет с рынком
   к воне на Upbit пробивают цель за сутки, доля от торгуемых, вариант с фильтром MA15 и с долей Кореи ≥ 20%,
   пересечения со входами журналов в те же сутки.
2. Наборы P&D-групп Telegram (La Morgia и др. 2017–2021; Hu и др. 2019–01.2022): сколько целей в наших периодах
   и сколько из них имели перп Binance в день события.

Запуск: python3 -I probe_freq.py; лог — probe_freq.log рядом."""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s183/study")
import common183 as C  # noqa: E402

R = "/home/user/mc_data/s188/repos"
DAY = 86400
K = 0.5


def breakout(per):
    d = pd.read_pickle(f"{C.OUT}/daily_{per}.pkl")
    bad = C.bad_set()
    d = d[~d.s.isin(bad)].sort_values(["s", "d"]).copy()
    g = d.groupby("s")
    d["ph"], d["pl"], d["pc"] = g.h.shift(1), g.l.shift(1), g.c.shift(1)
    d["pd"] = g.d.shift(1)
    d["ma15"] = g.c.transform(lambda x: x.shift(1).rolling(15, min_periods=15).mean())
    d = d[(d.pd == d.d - DAY) & (d.qv > 0)]
    up = d[d.krv_upbit.fillna(0) > 0].copy()                   # монета торгуется к воне на Upbit в эти сутки
    up["rng"] = (up.ph - up.pl) / up.o
    up["tgt"] = up.o + K * (up.ph - up.pl)
    up["bo"] = up.h > up.tgt
    up["bo_ma"] = up.bo & (up.o > up.ma15)
    kr = up.krv.fillna(0)
    up["kshare"] = kr / (kr + up.qv + up.sqv.fillna(0))
    up["bo_kr"] = up.bo & (up.kshare >= 0.20)
    t0, t1 = C.ts(C.PER[per]["t0"]), C.ts(C.PER[per]["t1"])
    up = up[(up.d >= t0) & (up.d < t1)]
    mon = C.months(per)
    days = up.d.nunique()
    J = C.journals(per)
    J["d"] = (J.t // DAY) * DAY
    jset = {}
    for j, x in J.groupby("j"):
        jset[j] = set(zip(x.s, x.d))
    allj = set(zip(J.s, J.d))
    print(f"\n== {per}: суток {days}, монет с рынком Upbit в сутки (медиана) {up.groupby('d').size().median():.0f}")
    for col, name in (("bo", "пробой k=0,5"), ("bo_ma", "пробой + открытие выше MA15"),
                      ("bo_kr", "пробой + доля Кореи в обороте суток ≥ 20%")):
        x = up[up[col]]
        per_day = x.groupby("d").size().reindex(sorted(up.d.unique()), fill_value=0)
        keys = set(zip(x.s, x.d))
        ov = {j: len(keys & v) / max(len(keys), 1) for j, v in jset.items()}
        print(f"  {name}: монето-суток {len(x)} ({len(x) / mon:.0f} в месяц; доля от торгуемых "
              f"{len(x) / len(up):.0%}); в сутки медиана {per_day.median():.0f}, p90 {per_day.quantile(.9):.0f}; "
              f"медиана прошлого размаха {x.rng.median():.1%}")
        print(f"    в те же сутки вход журнала: любой {len(keys & allj) / max(len(keys), 1):.0%}; "
              + ", ".join(f"{j} {v:.0%}" for j, v in sorted(ov.items(), key=lambda z: -z[1])))
    # обратное: доля входов ⏰ и 🔝, у которых монета в те же сутки пробила цель
    for j in ("⏰", "🔝", "👀", "🇰🇷"):
        if j not in jset:
            continue
        keys = jset[j]
        b = set(zip(up[up.bo].s, up[up.bo].d))
        print(f"  входы {j} с пробоем цели в те же сутки: {len(keys & b) / max(len(keys), 1):.0%} из {len(keys)}")


def pnd():
    lm = pd.read_csv(f"{R}/SystemsLab-Sapienza__pump-and-dump-dataset/pump_telegram.csv")
    lm["t"] = pd.to_datetime(lm.date + " " + lm.hour, utc=True)
    lm = lm.rename(columns={"symbol": "coin"})[["coin", "exchange", "t"]]
    hu = pd.read_csv(f"{R}/Bayi-Hu__Pump-and-Dump-Detection/Data/Telegram/Labeled/PD_logs_cleaned.txt", sep="\t")
    hu["t"] = pd.to_datetime(hu.timestamp, utc=True)
    hu = hu[["coin", "exchange", "t"]]
    print("\n== P&D-группы Telegram")
    for name, x in (("La Morgia и др.", lm), ("Hu и др.", hu)):
        print(f"  {name}: событий {len(x)}, {x.t.min():%Y-%m} … {x.t.max():%Y-%m}; биржи "
              + ", ".join(f"{k} {v}" for k, v in x.exchange.str.lower().value_counts().head(6).items()))
    allx = pd.concat([lm.assign(src="LM"), hu.assign(src="HU")])
    allx["coin"] = allx.coin.str.upper().str.strip()
    allx["d"] = [int(z.timestamp()) // DAY * DAY for z in allx.t]
    allx = allx.drop_duplicates(["coin", "d"])
    for per in C.PERS:
        t0, t1 = C.ts(C.PER[per]["t0"]), C.ts(C.PER[per]["t1"])
        x = allx[(allx.d >= t0) & (allx.d < t1)]
        if not len(x):
            print(f"  {per}: событий нет")
            continue
        dp = pd.read_pickle(f"{C.OUT}/daily_{per}.pkl")
        live = set(zip(dp[dp.qv > 0].s, dp[dp.qv > 0].d))
        hasp = [(c, d) in live for c, d in zip(x.coin, x.d)]
        months = (min(x.t.max().timestamp(), t1) - t0) / (30.4 * DAY)
        print(f"  {per}: событий {len(x)} (до {x.t.max():%Y-%m}; {len(x) / months:.1f} в месяц), с перпом Binance "
              f"в день события {sum(hasp)} ({sum(hasp) / months:.1f} в месяц); биржи событий с перпом: "
              + ", ".join(f"{k} {v}" for k, v in x[hasp].exchange.str.lower().value_counts().items()))
        print("    монеты с перпом:", ", ".join(sorted(set(x[hasp].coin))[:40]))


if __name__ == "__main__":
    if "pnd" not in sys.argv:
        for per in C.PERS:
            breakout(per)
    pnd()
