import numpy as np, pandas as pd
import fexit2 as X
from sim import FUND, SIG
# ставка за период выплаты, как её показывает Binance: (% в час) × длина периода
IH = {}
for s in SIG:
    key = (s["sym"], s["ep"]); F = FUND.get(s["sym"])
    if key not in X.PP or F is None or len(F) < 2: continue
    pt, pr = X.PP[key]; ih = np.empty(len(pt))
    for i, t in enumerate(pt):
        k = np.searchsorted(F[:, 0], t, "right") - 1
        ih[i] = (F[k + 1, 0] - F[k, 0]) / 3600 if k + 1 < len(F) else (F[k, 0] - F[k - 1, 0]) / 3600
    X.PP[key] = (pt, pr * ih)
rules = {"без досрочного выхода": None}
for th in (0.3, 0.5, 0.75, 1.0, 1.5, 2.0):
    rules[f"за период ≤ −{th}%"] = (lambda th: lambda pr, i, up: pr[i] <= -th)(th)
    for Y in (5, 10):
        rules[f"за период ≤ −{th}% и цена +{Y}%"] = (lambda th, Y: lambda pr, i, up: pr[i] <= -th and up >= Y / 100)(th, Y)
for tp, sl in ((15, 25), (6, 20)):
    print(f"\n===== {tp}/{sl} =====")
    for lab, rule in rules.items():
        x = X.run(tp, sl, rule); vc = x.kind.value_counts(); mid = x.ep.median()
        print(f"{lab:36s} итого {x.pnl.sum():+7.1f} (1-я пол. {x[x.ep<mid].pnl.sum():+5.1f} / 2-я {x[x.ep>=mid].pnl.sum():+5.1f}) | стопов {vc.get('стоп',0):3d}, досрочно {vc.get('фандинг',0):3d} | просадка {(x.pnl.cumsum()-x.pnl.cumsum().cummax()).min():+.1f}")
