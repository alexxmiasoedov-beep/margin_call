"""s189 — сводка Г1 (Gate 16:00), Г2 (FTX 00:00) и Г3 (лестница порогов Gate) по s189_<период>.pkl.
Запуск: python3 <repo>/research/s189/report.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s182"))
import common182 as C  # noqa: E402

OUT = C.OUT
OTH = [0, 4, 8, 12, 20]


def line(x, per, col="net4"):
    y = x[x[col].notna()].rename(columns={col: "net", "stop4": "why"}).copy()
    y["why"] = np.where(y.why.astype(bool), "стоп", "время")
    y["hed"] = x.loc[y.index, "hed4"]; y["pl"] = x.loc[y.index, "pl4"]; y["t"] = x.loc[y.index, "T"]
    return C.line(y, per)


def delta(e, c, col="net4"):
    z = pd.concat([e.assign(ev=1), c.assign(ev=0)])
    z = z[z[col].notna()]
    d, se = C.diff(z[col], z.ev, z["T"])
    return d, se


def block(A, name, ev, ctl, pers, col="net4"):
    print(f"\n{name}")
    parts = []
    for per in pers:
        X = A[per]
        e, c = X[ev(X)], X[ctl(X)]
        d, se = delta(e, c, col)
        parts.append((d, se, int(e[col].notna().sum())))
        print(f"  {per}: события {line(e, per, col)}")
        print(f"  {' ' * len(per)}  контроль {line(c, per, col)}")
        print(f"  {' ' * len(per)}  Δ = {d:+.2%} (t {d / se:+.1f})")
    m, t = C.combine(parts)
    print(f"  вместе: Δ = {m:+.2%} (t {t:+.1f})")
    return m, t


def main():
    A = {per: pd.read_pickle(f"{OUT}/s189_{per}.pkl") for per in C.PER}
    for X in A.values():
        X["T"] = X["T"].astype(np.int64)
        for c in ("gate", "ftx", "blvt", "ftx_coin", "krw"):
            X[c] = X[c].fillna(False).astype(bool)
    P3 = list(C.PER)
    a = lambda X: X.kind == "a"  # noqa: E731
    print("s189 — ребаланс токенов с плечом; доход на сделку после комиссии и фандинга, стоп 15%")
    # Г1
    block(A, "Г1 — Gate 16:00, шорт после r24 ≥ 10%, 4 ч; контроль (а) — те же монеты в 00/04/08/12/20 UTC",
          lambda X: a(X) & (X.H == 16) & X.gate & (X.side < 0), lambda X: a(X) & X.H.isin(OTH) & X.gate & (X.side < 0), P3)
    block(A, "Г1 зеркало — лонг после r24 ≤ −10% в 16:00 против тех же якорей",
          lambda X: a(X) & (X.H == 16) & X.gate & (X.side > 0), lambda X: a(X) & X.H.isin(OTH) & X.gate & (X.side > 0), P3)
    block(A, "Г1 контроль (б) — монеты без токенов Gate в 16:00",
          lambda X: a(X) & (X.H == 16) & X.gate & (X.side < 0), lambda X: a(X) & (X.H == 16) & ~X.gate & (X.side < 0), P3)
    for col in ("net1", "net24"):
        block(A, f"Г1 выход {col[3:]} ч",
              lambda X: a(X) & (X.H == 16) & X.gate & (X.side < 0), lambda X: a(X) & X.H.isin(OTH) & X.gate & (X.side < 0),
              P3, col)
    print("\nГ1 разрезы (события 16:00; Δ к контролю (а)):")
    for name, f in (("φ < 0,3%", lambda X: X.phi_g < 0.003), ("φ 0,3–1%", lambda X: (X.phi_g >= 0.003) & (X.phi_g < 0.01)),
                    ("φ ≥ 1%", lambda X: X.phi_g >= 0.01), ("до 01.04.2025", lambda X: X["T"] < C.ts("2025-04-01")),
                    ("после 01.04.2025", lambda X: X["T"] >= C.ts("2025-04-01")), ("рынок к воне есть", lambda X: X.krw),
                    ("рынка к воне нет", lambda X: ~X.krw.astype(bool)),
                    ("выходные", lambda X: pd.to_datetime(X["T"], unit="s").dt.weekday.values >= 5)):
        out = []
        for per in P3:
            X = A[per]
            e = X[a(X) & (X.H == 16) & X.gate & (X.side < 0) & f(X)]
            c = X[a(X) & X.H.isin(OTH) & X.gate & (X.side < 0)]
            if e.net4.notna().sum() < 5:
                out.append(f"n={int(e.net4.notna().sum())}"); continue
            d, se = delta(e, c)
            out.append(f"n={int(e.net4.notna().sum()):4d} {e.net4.mean():+.2%} Δ {d:+.2%} (t {d / se:+.1f})")
        print(f"  {name:20s} " + " | ".join(out))
    # Г2
    block(A, "Г2 — FTX 00:00, шорт после r24 ≥ 10%, 4 ч; контроль (а) — те же монеты в 04/08/12/16/20 UTC",
          lambda X: a(X) & (X.H == 0) & X.ftx & (X.side < 0), lambda X: a(X) & X.H.isin([4, 8, 12, 16, 20]) & X.ftx & (X.side < 0),
          ["2020–2022"])
    block(A, "Г2 зеркало — лонг после r24 ≤ −10%",
          lambda X: a(X) & (X.H == 0) & X.ftx & (X.side > 0), lambda X: a(X) & X.H.isin([4, 8, 12, 16, 20]) & X.ftx & (X.side > 0),
          ["2020–2022"])
    block(A, "Г2 плацебо по времени — монеты FTX в 00 UTC без FTX (10.2022–09.2024)",
          lambda X: a(X) & (X.H == 0) & X.ftx_coin & ~X.ftx & (X.side < 0),
          lambda X: a(X) & X.H.isin([4, 8, 12, 16, 20]) & X.ftx_coin & ~X.ftx & (X.side < 0), ["2022–2024"])
    block(A, "Г2 контроль (б) — монеты без токенов FTX и BLVT в 00 UTC",
          lambda X: a(X) & (X.H == 0) & X.ftx & (X.side < 0), lambda X: a(X) & (X.H == 0) & ~X.ftx & ~X.blvt & (X.side < 0),
          ["2020–2022"])
    X = A["2020–2022"]
    print("  доза (поток к обороту свечи 00:00–00:15):", " | ".join(
        f"{nm}: n={int(m.sum())} {X[m].net4.mean():+.2%}" for nm, m in (
            ("< 0,5", a(X) & (X.H == 0) & X.ftx & (X.side < 0) & (X.phi_f < 0.5)),
            ("0,5–2", a(X) & (X.H == 0) & X.ftx & (X.side < 0) & (X.phi_f >= 0.5) & (X.phi_f < 2)),
            ("≥ 2", a(X) & (X.H == 0) & X.ftx & (X.side < 0) & (X.phi_f >= 2)))))
    # Г3
    block(A, "Г3 — лестница порогов Gate от 16:00, шорт 4 ч; контроль — ложный якорь 04/08/12 UTC",
          lambda X: (X.kind == "g3") & (X.H == 16), lambda X: (X.kind == "g3") & X.H.isin([4, 8, 12]), P3)


if __name__ == "__main__":
    main()
