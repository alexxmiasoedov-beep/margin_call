"""Журнал «отдача займа → шорт»: монета в маржинальном боте (MarginData) непрерывно ≥ 6 ч, отдача за 24 ч (REP) выросла в ≥ 2 раза
за час (и на ≥ 20 тыс. $), цена фьючерса за сутки изменилась на ≥ 10% в любую сторону → шорт на закрытии 15-мин свечи.
Сетка тейк/стоп, месяцы, просадка, серии, одновременные позиции (маржа 1 USDT × 10)."""
import pickle, re
import numpy as np, pandas as pd
R = pd.read_pickle("s9/repay_rule.pkl").sort_values("t")
K = pickle.load(open("s2/k2y.pkl", "rb"))
print("сделок:", len(R), "с", pd.to_datetime(R.t.min(), unit="s").date(), "по", pd.to_datetime(R.t.max(), unit="s").date(),
      f"({len(R) / ((R.t.max() - R.t.min()) / 86400 / 30.4):.1f} в месяц)")
grid = [c for c in R.columns if c.startswith("S_")]
G = pd.DataFrame([(c, R[c].mean(), (R[c] > 0).mean(), R[R.half == 1][c].mean(), R[R.half == 2][c].mean()) for c in grid],
                 columns=["вариант", "на сделку", "винрейт", "1-я", "2-я"]).sort_values("на сделку", ascending=False)
print(G.head(12).round(4).to_string(index=False))
def exit_time(s, t, tp, sl, hold=192):
    a = K[s]; j = int(np.searchsorted(a["t"], t, "right") - 1); e = float(a["c"][j]); end = min(j + hold, len(a["t"]) - 1)
    hi = a["h"][j + 1:end + 1] / e - 1; lo = a["l"][j + 1:end + 1] / e - 1
    b = np.flatnonzero(hi >= sl); g = np.flatnonzero(lo <= -tp); q = min(b[0] if len(b) else 10**9, g[0] if len(g) else 10**9)
    return a["t"][j + 1 + q] + 900 if q < 10**9 else a["t"][end] + 900
for col in ("S_10_25", "S_7_20", "S_10_10", "S_15_25"):
    if col not in R: continue
    tp, sl = (int(x) / 100 for x in col.split("_")[1:])
    u = R[col].values * 10; eq = np.cumsum(u); dd = (eq - np.maximum.accumulate(eq)).min()
    out = [exit_time(s, t, tp, sl) for s, t in zip(R.s, R.t)]
    ev = sorted([(t, 1) for t in R.t] + [(t, -1) for t in out]); cur = mx = 0
    for _, x in ev: cur += x; mx = max(mx, cur)
    mo = R.groupby(pd.to_datetime(R.t, unit="s").dt.strftime("%y-%m"))[col].sum() * 10
    qm = R.groupby("q")[col].mean()
    streak = mxs = 0
    for v in R[col].values: streak = streak + 1 if v <= 0 else 0; mxs = max(mxs, streak)
    print(f"{col}: WR {(R[col] > 0).mean():.1%}, {R[col].mean()*100:+.2f}% на сделку, итог {u.sum():+.1f} USDT, просадка {dd:+.1f}, "
          f"месяцев в плюсе {(mo > 0).sum()}/{len(mo)}, кварталов {(qm > 0).sum()}/{len(qm)}, одновременно до {mx}, серия убытков {mxs}")
print("по месяцам (S_10_25, USDT):", (R.groupby(pd.to_datetime(R.t, unit="s").dt.strftime("%y-%m")).S_10_25.sum() * 10).round(1).to_dict())
print("после роста (сутки ≥ +10%):", (R.c_r24 > 0).sum(), f"{R[R.c_r24 > 0].S_10_25.mean()*100:+.2f}%", "| после падения:", (R.c_r24 < 0).sum(), f"{R[R.c_r24 < 0].S_10_25.mean()*100:+.2f}%")
