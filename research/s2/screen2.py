"""Двумерный отсев: средняя доходность к рынку через 24 ч (f24a) и 72 ч (f72a) в клетках двух признаков, по годам."""
import numpy as np, pandas as pd
P = pd.read_pickle("s2/panel_liq.pkl")
def two(name, k1, b1, k2, b2, fwd="f24a", min_n=300):
    a = pd.cut(P[k1], b1); b = pd.cut(P[k2], b2)
    g = P.groupby([a, b], observed=True)
    rows = []
    for (x, y), d in g:
        if len(d) < min_n: continue
        dm = d.groupby("day")[fwd].mean(); ts = dm.mean() / (dm.std() / np.sqrt(len(dm))) if len(dm) > 5 else np.nan
        yr = d.groupby("year")[fwd].mean()
        rows.append((str(x), str(y), len(d), d.s.nunique(), round(d[fwd].mean() * 100, 2), round(ts, 1), " ".join(f"{k}:{v * 100:+.2f}" for k, v in yr.items())))
    print(f"\n=== {name} → {fwd}")
    print(pd.DataFrame(rows, columns=[k1, k2, "N", "монет", "к рынку %", "t", "по годам"]).to_string(index=False))
two("Объём ×7 дн и рост за сутки", "volr", [0, 1.2, 2, 4, 1000], "r24", [-1, -0.1, 0, 0.1, 0.25, 100])
two("Рост за сутки и фандинг за сутки", "r24", [-1, -0.1, 0, 0.1, 0.25, 100], "fund24", [-1, -0.003, -0.0005, 0.0001, 0.0005, 1])
two("Дисбаланс тейкеров 4 ч и рост за 4 ч", "d4", [-1, -0.05, 0, 0.05, 1], "r4", [-1, -0.05, -0.02, 0.02, 0.05, 1], "f24a")
two("Удаление от максимума суток и объём", "fromhi", [-1, -0.2, -0.1, -0.03, 0.001], "volr", [0, 1.2, 2, 4, 1000])
