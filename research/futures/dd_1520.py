"""Просадка и кварталы журнала 15/20 (📕) на прежних и исправленных сигналах правил 1 и 2 — тот же run_p, что в analyze_scan_full.py."""
import os, sys, datetime, pickle
import numpy as np, pandas as pd
UTC = datetime.timezone.utc; CUT = datetime.datetime(2026, 9, 28, tzinfo=UTC).timestamp()
q = lambda ep: f"{datetime.datetime.fromtimestamp(ep, UTC).year}Q{(datetime.datetime.fromtimestamp(ep, UTC).month - 1) // 3 + 1}"
for f in ("signals_scan_full.pkl", "signals_scan_plus.pkl"):
    os.environ["SIGFILE"] = f
    for m in ("sim", "realism"): sys.modules.pop(m, None)
    import sim, realism as R
    src = open("analyze_scan_full.py").read(); ns = {"np": np, "pd": pd, "R": R, "SIG": sim.SIG, "FUND": sim.FUND}
    exec(src[src.index("def run_p"):src.index("CFG = ")], ns)
    for lab, tp, sl in (("15/20 📕", 15, 20), ("6/20 📙", 6, 20)):
        x = ns["run_p"](lambda fh: (tp, sl), 1, t_to=CUT, sig=sim.SIG)
        eq = x.sort_values("ep").pnl.cumsum(); dd = (eq - eq.cummax()).min(); qs = x.groupby(x.ep.map(q)).pnl.sum()
        print(f"{f:24s} {lab}: n={len(x)} итого {x.pnl.sum():+.1f} просадка {dd:.1f} кварталов в плюсе {(qs > 0).sum()}/{len(qs)} худший {qs.min():+.1f}")
