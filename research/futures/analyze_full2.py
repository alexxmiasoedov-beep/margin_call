import os
os.environ.setdefault("SIGFILE", "signals_full.pkl")
import numpy as np, pandas as pd
from analyze_full import run_p
pd.set_option("display.width", 250)
CFG = [("6/20", lambda fh: (6, 20)), ("10/20", lambda fh: (10, 20)), ("15/20", lambda fh: (15, 20)), ("20/20", lambda fh: (20, 20)),
       ("15/25", lambda fh: (15, 25)), ("📗", lambda fh: (15, 25) if fh is not None and fh * 100 < -0.03 else (6, 20))]
print("Значимость: среднее на сделку ± 2 ст. ошибки (если интервал целиком > 0 — преимущество доказано)")
Q = {}
for lab, p in CFG:
    x = run_p(p); x["q"] = pd.to_datetime(x.ep, unit="s").dt.to_period("Q").astype(str)
    for r, nm in (("1", "правило 1"), ("2", "правило 2"), (None, "оба")):
        y = x if r is None else x[x.rule == r]
        m, se = y.pnl.mean(), y.pnl.std() / np.sqrt(len(y))
        mid = y.ep.median()
        print(f"  {lab:6s} {nm:10s} n={len(y):4d}  {m:+.3f} ± {2*se:.3f}  t={m/se:+.1f} | 1-я пол. {y[y.ep<mid].pnl.sum():+6.1f}, 2-я {y[y.ep>=mid].pnl.sum():+6.1f} | фандинг {y.fund.sum():+6.1f}")
        if r: Q[(lab, nm)] = y.groupby("q").pnl.sum().round(1)
print("\nПо кварталам:")
print(pd.DataFrame(Q).to_string())
