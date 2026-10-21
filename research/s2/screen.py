"""Отсев гипотез на панели: средняя будущая доходность (сырая и относительно рынка в тот же момент) по корзинам признака,
t-статистика по дням (среднее корзины за день → t-тест по дням), по годам. Только ликвидные: объём за сутки ≥ 5 млн $."""
import sys, datetime
import numpy as np, pandas as pd
P = pd.read_pickle("s2/panel.pkl")
P["t"] = (np.round(P.t.astype(np.float64) / 14400) * 14400).astype(np.int64)
P = P[P.v24 >= 5e6].copy()
for f in ("f4", "f24", "f72"):
    P[f + "a"] = P[f] - P.groupby("t")[f].transform("mean")
P["day"] = (P.t // 86400).astype(np.int64); P["year"] = pd.to_datetime(P.t, unit="s").dt.year
P.to_pickle("s2/panel_liq.pkl")
def screen(name, key, bins, fwd="f24a"):
    x = P[key]; cut = pd.cut(x, bins); g = P.groupby(cut, observed=True)
    rows = []
    for b, d in g:
        dm = d.groupby("day")[fwd].mean(); tstat = dm.mean() / (dm.std() / np.sqrt(len(dm))) if len(dm) > 5 else np.nan
        y = d.groupby("year")[fwd].mean()
        rows.append((str(b), len(d), d.s.nunique(), d[fwd.rstrip("a")].mean() * 100, d[fwd].mean() * 100, tstat,
                     " ".join(f"{k}:{v * 100:+.2f}" for k, v in y.items())))
    print(f"\n=== {name}: {key} → {fwd}")
    print(pd.DataFrame(rows, columns=["корзина", "N", "монет", "сырая %", "к рынку %", "t (дни)", "по годам к рынку"]).to_string(index=False))
if __name__ == "__main__":
    print("строк", len(P), "| монет", P.s.nunique(), "| моментов", P.t.nunique())
    screen("Разворот/импульс", "r24", [-1, -0.2, -0.1, -0.05, 0, 0.05, 0.1, 0.2, 0.4, 100])
    screen("Разворот/импульс 3 сут", "r72", [-1, -0.3, -0.15, -0.05, 0.05, 0.15, 0.3, 0.6, 100], "f72a")
    screen("Дисбаланс тейкеров 24 ч", "d24", [-1, -0.1, -0.05, -0.02, 0, 0.02, 0.05, 0.1, 1])
    screen("Фандинг за 3 сут", "fund72", [-1, -0.03, -0.01, -0.003, -0.001, 0, 0.0003, 0.001, 0.003, 1], "f72a")
    screen("Возраст фьючерса, дней", "age", [0, 3, 7, 14, 30, 60, 120, 240, 10000], "f72a")
    screen("Объём суток к среднему за неделю", "volr", [0, 0.5, 0.8, 1.2, 2, 4, 8, 1000])
    screen("Размах суток", "rng24", [0, 0.05, 0.1, 0.2, 0.4, 0.8, 100])
