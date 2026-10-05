import os
os.environ.setdefault("SIGFILE", "signals_full.pkl")
import numpy as np, pandas as pd
import analyze_full as A
from sim import SIG
pd.set_option("display.width", 250)
rb = {(s["sym"], s["ep"]): s["rise_before"] for s in SIG}
print("ПРАВИЛО 2 — сетка (итого | 1-я / 2-я половина | просадка):")
for tp in (6, 10, 15, 20, None):
    for sl in (20, 25):
        x = A.run_p(lambda fh, tp=tp, sl=sl: (tp, sl)); y = x[x.rule == "2"]; mid = y.ep.median()
        dd = (y.pnl.cumsum() - y.pnl.cumsum().cummax()).min()
        print(f"  {str(tp or 'нет'):>3s}/{sl}: {y.pnl.sum():+6.1f} | {y[y.ep<mid].pnl.sum():+6.1f} / {y[y.ep>=mid].pnl.sum():+6.1f} | {dd:+.1f}")
for lab, p in (("6/20", lambda fh: (6, 20)), ("15/25", lambda fh: (15, 25))):
    x = A.run_p(p); y = x[x.rule == "2"].copy(); y["rb"] = [rb[(a, b)] for a, b in zip(y.sym, y.ep)]; mid = y.ep.median()
    print(f"\nПРАВИЛО 2, {lab}: рост за 20 ч до падения")
    for lo, hi, nm in ((30, 1e9, ">30%"), (15, 30, "15–30%"), (5, 15, "5–15%"), (-1e9, 5, "<5%")):
        g = y[(y.rb >= lo) & (y.rb < hi)]
        print(f"  {nm:7s} n={len(g):4d} тейк {(g.kind=='тейк').mean()*100:3.0f}% стоп {(g.kind=='стоп').mean()*100:3.0f}% | на сделку {g.pnl.mean():+.3f} | 1-я пол. {g[g.ep<mid].pnl.sum():+6.1f}, 2-я {g[g.ep>=mid].pnl.sum():+6.1f}")
