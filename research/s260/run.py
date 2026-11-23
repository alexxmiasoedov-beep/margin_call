"""s260 — Г5 s259 «тень-вынос вверх» у перпов без спота Binance → шорт 24 ч, стоп 25% (зеркало: тень вниз → лонг 24 ч).
Правило и порог — ВЫВОДЫ.md (записаны до расчёта доходов). Свеча 15 мин: максимум ≥ открытия +10% и закрытие в нижней
половине размаха (тень вверх) или минимум ≤ открытия −10% и закрытие в верхней половине (тень вниз), как s259/cascade.wicks;
перп без спота Binance на момент закрытия свечи, старше суток; у монеты не чаще одного события вида за 24 ч.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s260/run.py [count|main]"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nospot as N  # noqa: E402

HOLD, SL = 24, 0.25
KINDS = {"up": -1, "dn": +1}            # тень вверх → шорт, тень вниз → лонг


def events(group="ns"):
    """group: «ns» — перпы без спота (гипотеза), «sp» — монеты со спотом (для отчёта)."""
    U = N.universe()
    rows = []
    for s, u in U.items():
        a = N.K[s]
        t = a["t"].astype(np.int64); te = t + N.BAR
        o, h, l, c, qv = (a[x].astype(float) for x in ("o", "h", "l", "c", "qv"))
        rng = np.maximum(h - l, 1e-12)
        ns = N.nospot_mask(u, te)
        grp = ns if group == "ns" else ((te >= (u["spot0"] or np.inf)) & (te - u["live0"] >= N.DAY))
        base = (qv > 0) & grp & (te >= N.T0) & (te <= N.TB)
        cq = pd.Series(qv).rolling(672, min_periods=96).sum().shift(1).values / 7          # оборот за сутки по 7 сут
        for kind in KINDS:
            m = base & ((h >= o * 1.10) & (c <= l + 0.5 * rng) if kind == "up" else (l <= o * 0.90) & (c >= l + 0.5 * rng))
            I = np.flatnonzero(m)
            if not len(I):
                continue
            I = I[N.cooldown(te[I], N.DAY)]
            for i in I:
                rows.append((s, int(i), int(te[i]), kind, float(cq[i]) if np.isfinite(cq[i]) else np.nan,
                             (h[i] / o[i] - 1) if kind == "up" else (1 - l[i] / o[i])))
    E = pd.DataFrame(rows, columns=["s", "i", "te", "kind", "to7", "wick"])
    E["per"] = N.period(E.te, HOLD)
    return E[E.per.notna()].reset_index(drop=True)


def count():
    E = events("ns")
    mA = (N.TA - N.T0) / N.MONTH
    for kind in KINDS:
        x = E[E.kind == kind]
        A, B = x[x.per == "А"], x[x.per == "Б"]
        mid = float(np.median(A.te))
        h2 = A[A.te >= mid]
        print(f"{kind}: А — {len(A)} ({len(A) / mA:.1f} в месяц), монет {A.s.nunique()}; середина А "
              f"{pd.Timestamp(mid, unit='s').date()}, 2-я половина {len(h2) / ((N.TA - mid) / N.MONTH):.1f} в месяц; "
              f"Б — {len(B)} ({len(B) / ((N.TB - N.TA) / N.MONTH):.1f} в месяц), монет {B.s.nunique()}")
        print("   по кварталам:", pd.to_datetime(x.te, unit="s").dt.to_period("Q").value_counts().sort_index().to_dict())


def main():
    mA = (N.TA - N.T0) / N.MONTH
    mB = (N.TB - HOLD * 3600 - N.TA) / N.MONTH
    E = events("ns")
    R = {}
    for kind, side in KINDS.items():
        X = N.trades(E[E.kind == kind], side, HOLD, SL)
        R[kind] = X
        A, B = X[X.per == "А"], X[X.per == "Б"]
        mid = float(np.median(A.te))
        nm = "Г5: тень вверх → шорт 24 ч" if kind == "up" else "зеркало: тень вниз → лонг 24 ч"
        print(f"\n### {nm}")
        print(f"А (10.2024–18.10.2026): {N.line(A, mA, mid)}")
        print(f"  1-я половина: {N.line(A[A.te < mid], mA / 2)}")
        print(f"  2-я половина: {N.line(A[A.te >= mid], mA / 2)}")
        print(f"Б (19.10–19.11.2026): {N.line(B, mB)}")
        edges = [2.3e6, 5.3e6, 12.4e6, 41.5e6]                        # пятые доли оборота s259
        bk = np.searchsorted(edges, A.to7.fillna(0).values)
        for b in range(5):
            print(f"  А, оборот {b + 1}/5: {N.line(A[bk == b], mA)}")
        q = A.wick.quantile([1 / 3, 2 / 3]).values
        print(f"  А, тень < {q[0]:.0%}: {N.line(A[A.wick < q[0]], mA)}")
        print(f"  А, тень ≥ {q[1]:.0%}: {N.line(A[A.wick >= q[1]], mA)}")
        N.verdict(A, B, nm)
    pd.concat([x.assign(kind=k) for k, x in R.items()]).to_pickle("s260_trades.pkl")
    print("\n### для отчёта: то же у монет со спотом (А)")
    S = events("sp")
    for kind, side in KINDS.items():
        X = N.trades(S[(S.kind == kind) & (S.per == "А")], side, HOLD, SL)
        print(f"  {kind}: {N.line(X, mA, float(np.median(X.te)) if len(X) else None)}")


if __name__ == "__main__":
    {"count": count, "main": main}[sys.argv[1] if len(sys.argv) > 1 else "count"]()
