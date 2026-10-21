"""Часы фандинга: что делает цена вокруг выплаты, когда ставка экстремальна. Вход за 15 мин / 1 ч до выплаты, выход через 15 мин
/ 1 ч после. Лонг получает выплату при отрицательной ставке (и платит при положительной), шорт — наоборот. Комиссия 0,1%."""
import pickle, datetime
import numpy as np, pandas as pd
K = pickle.load(open("s2/k2y.pkl", "rb")); F = pickle.load(open("s2/fund2y.pkl", "rb"))
UTC = datetime.timezone.utc
T0 = datetime.datetime(2024, 10, 19, tzinfo=UTC).timestamp(); T1 = datetime.datetime(2026, 10, 18, tzinfo=UTC).timestamp()
R = []
for s, fr in F.items():
    a = K.get(s)
    if a is None: continue
    t = a["t"]; c = a["c"].astype(np.float64); n = len(t); idx = {int(x): i for i, x in enumerate(t)}
    for ts, iv, rate in fr:
        if not (T0 <= ts <= T1) or abs(rate) < 0.0005: continue
        j = idx.get(int(ts) // 900 * 900 - 900)              # свеча, закрывшаяся в момент выплаты (выплата с точностью до секунд)
        if j is None or j < 8 or j + 8 >= n: continue
        R.append((s, ts, iv, rate, c[j - 4], c[j - 1], c[j], c[j + 1], c[j + 4], c[j + 16] if j + 16 < n else np.nan))
D = pd.DataFrame(R, columns=["s", "ts", "iv", "rate", "c_m60", "c_m15", "c_0", "c_p15", "c_p60", "c_p4h"])
D["pre60"] = D.c_0 / D.c_m60 - 1; D["post60"] = D.c_p60 / D.c_0 - 1; D["post4h"] = D.c_p4h / D.c_0 - 1
D["long_15_15"] = D.c_p15 / D.c_m15 - 1 - D.rate - 0.001; D["long_60_60"] = D.c_p60 / D.c_m60 - 1 - D.rate - 0.001
D["short_after"] = 1 - D.c_p60 / D.c_p15 - 0.001                     # шорт сразу после выплаты на час (выплату не платит)
D["year"] = pd.to_datetime(D.ts, unit="s").dt.year
D.to_pickle("s2/fund_settle.pkl")
bins = [-1, -0.015, -0.0075, -0.004, -0.002, -0.001, -0.0005, 0.0005, 0.001, 0.002, 1]
D["bin"] = pd.cut(D.rate, bins)
g = D.groupby("bin", observed=True)
out = g.agg(N=("rate", "size"), монет=("s", "nunique"), ставка=("rate", "mean"), до_выплаты_1ч=("pre60", "mean"), после_1ч=("post60", "mean"),
            после_4ч=("post4h", "mean"), лонг_15_15=("long_15_15", "mean"), лонг_60_60=("long_60_60", "mean"), шорт_после=("short_after", "mean"))
pd.set_option("display.width", 250); print((out * [1, 1, 100, 100, 100, 100, 100, 100, 100]).round(3).to_string())
print("\nпо годам, лонг 15 мин до → 15 мин после, ставка ≤ −0,4%:")
print((D[D.rate <= -0.004].groupby("year").long_15_15.agg(["size", "mean"]) * [1, 100]).round(3).to_string())
