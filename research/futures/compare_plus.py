"""Правила 1 и 2: сигналы с исправленным разбором строк (CHNG со знаком «+», signals_scan_plus.pkl) против прежних
(signals_scan_full.pkl). Общие, только новые, только прежние (сдвинулись из-за кулдауна 24 ч) — исход каждой сделки отдельно
(realism.trade2: вход в минуту сигнала, стоп по марк-цене с проскальзыванием 0,2%, фактический фандинг)."""
import os, pickle, datetime
os.environ["SIGFILE"] = "signals_scan_plus.pkl"
import numpy as np, pandas as pd
import sim, realism as R
UTC = datetime.timezone.utc
A = pickle.load(open("signals_scan_full.pkl", "rb")); B = pickle.load(open("signals_scan_plus.pkl", "rb"))
for k, v in A["fund"].items():
    sim.FUND.setdefault(k, v)
ka = {(s["sym"], s["ep"]): s for s in A["sig"]}; kb = {(s["sym"], s["ep"]): s for s in B["sig"]}
sets = (("общие", sorted(ka.keys() & kb.keys()), kb), ("только с «+» (новые)", sorted(kb.keys() - ka.keys()), kb),
        ("только прежние (ушли)", sorted(ka.keys() - kb.keys()), ka))
for nm, keys, src in sets:
    r1 = sum(src[k]["rule"] == "1" for k in keys)
    ms = pd.Series([datetime.datetime.fromtimestamp(k[1], UTC).strftime("%y%m") for k in keys]).value_counts().sort_index()
    print(f"{nm}: {len(keys)} (правило 1 — {r1}, правило 2 — {len(keys) - r1}); по месяцам: " + " ".join(f"{m}:{n}" for m, n in ms.items()))
print()
for lab, tp, sl in (("6/20 📙", 6, 20), ("10/25", 10, 25), ("15/20 📕", 15, 20), ("15/25 📘", 15, 25), ("без тейка/25 📓", None, 25)):
    row = []
    for nm, keys, src in sets:
        x = [R.trade2(src[k], tp, sl, delay=1, slip_sl=0.002) for k in keys]
        p = np.array([y["pnl"] for y in x if y])
        row.append(f"{nm.split()[0]} n={len(p)} {p.mean():+.3f} WR {(p > 0).mean():.0%} Σ {p.sum():+.1f}" if len(p) else f"{nm.split()[0]} —")
    print(f"{lab:16s} | " + " | ".join(row))
