"""s261 — Г1 s259 «дисконт: индекс догоняет вниз» у перпов без спота Binance → шорт 24 ч, стоп 25%.
Правило и порог — ВЫВОДЫ.md (записаны до расчёта доходов). Событие — закрытие 15-мин свечи с премией к индексу p ≤ −2%
(premiumIndexKlines, закрытие свечи: s12/prem.pkl для А, s261/prem_b.pkl для Б), перп без спота Binance, старше суток;
не в первые 2 ч после пампа или обвала монеты (+15% / −15% за ≤ 2 ч из покоя, s260/nospot.pumps, dumps) — только
прошлое, без заглядывания; у монеты не чаще одного события за 24 ч.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s261/run.py [count|main]"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s260"))
import nospot as N  # noqa: E402

HOLD, SL, TH = 24, 0.25, -0.02


def premium():
    PR = pickle.load(open("s12/prem.pkl", "rb"))
    PB = pickle.load(open("s261/prem_b.pkl", "rb")) if os.path.exists("s261/prem_b.pkl") else {}
    out = {}
    for s in set(PR) | set(PB):
        parts = [v for v in (PR.get(s), PB.get(s)) if v is not None]
        t = np.concatenate([p[0] for p in parts]).astype(np.int64)
        p = np.concatenate([p[1] for p in parts]).astype(float)
        t, k = np.unique(t, return_index=True)
        out[s] = (t, p[k])
    return out


def events():
    U = N.universe()
    P = premium()
    rows = []
    for s, u in U.items():
        if s not in P:
            continue
        a = N.K[s]
        t = a["t"].astype(np.int64); te = t + N.BAR
        pt, pv = P[s]
        ip = np.searchsorted(pt, t); ip2 = np.minimum(ip, len(pt) - 1)
        has = (ip < len(pt)) & (pt[ip2] == t)
        p = np.where(has, pv[ip2], np.nan)
        m = has & (p <= TH) & (a["qv"] > 0) & N.nospot_mask(u, te) & (te >= N.T0) & (te <= N.TB)
        if not m.any():
            continue
        near = np.zeros(len(t), bool)                                    # пампы и обвалы: свеча события и 2 ч после
        for j in np.r_[N.pumps(a), N.dumps(a)]:
            near[j:j + 9] = True
        I = np.flatnonzero(m & ~near)
        if not len(I):
            continue
        I = I[N.cooldown(te[I], N.DAY)]
        cq = pd.Series(a["qv"].astype(float)).rolling(672, min_periods=96).sum().shift(1).values / 7
        for i in I:
            rows.append((s, int(i), int(te[i]), float(p[i]), float(cq[i]) if np.isfinite(cq[i]) else np.nan))
    E = pd.DataFrame(rows, columns=["s", "i", "te", "p", "to7"])
    E["per"] = N.period(E.te, HOLD)
    return E[E.per.notna()].reset_index(drop=True)


def count():
    E = events()
    mA = (N.TA - N.T0) / N.MONTH
    A, B = E[E.per == "А"], E[E.per == "Б"]
    mid = float(np.median(A.te))
    print(f"А — {len(A)} ({len(A) / mA:.1f} в месяц), монет {A.s.nunique()}; середина {pd.Timestamp(mid, unit='s').date()}, "
          f"2-я половина {(A.te >= mid).sum() / ((N.TA - mid) / N.MONTH):.1f} в месяц; Б — {len(B)}, монет {B.s.nunique()} "
          f"(премия Б {'есть' if os.path.exists('s261/prem_b.pkl') else 'ещё не загружена'})")
    print("по кварталам:", pd.to_datetime(E.te, unit="s").dt.to_period("Q").value_counts().sort_index().to_dict())
    print("p ≤ −5%:", (A.p <= -0.05).sum())


def main():
    mA = (N.TA - N.T0) / N.MONTH
    mB = (N.TB - HOLD * 3600 - N.TA) / N.MONTH
    E = events()
    X = N.trades(E, -1, HOLD, SL)
    X.to_pickle("s261_trades.pkl")
    A, B = X[X.per == "А"], X[X.per == "Б"]
    mid = float(np.median(A.te))
    print("### Г1: дисконт p ≤ −2% → шорт 24 ч")
    print(f"А (10.2024–18.10.2026): {N.line(A, mA, mid)}")
    print(f"  1-я половина: {N.line(A[A.te < mid], mA / 2)}")
    print(f"  2-я половина: {N.line(A[A.te >= mid], mA / 2)}")
    print(f"Б (19.10–19.11.2026): {N.line(B, mB)}")
    print(f"  А, p ≤ −5%: {N.line(A[A.p <= -0.05], mA)}")
    print(f"  А, −5% < p ≤ −2%: {N.line(A[A.p > -0.05], mA)}")
    edges = [2.3e6, 5.3e6, 12.4e6, 41.5e6]
    bk = np.searchsorted(edges, A.to7.fillna(0).values)
    for b in range(5):
        print(f"  А, оборот {b + 1}/5: {N.line(A[bk == b], mA)}")
    N.verdict(A, B, "Г1")


if __name__ == "__main__":
    {"count": count, "main": main}[sys.argv[1] if len(sys.argv) > 1 else "count"]()
