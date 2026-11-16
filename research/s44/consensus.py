"""s44 — согласие журналов (гипотеза — ВЫВОДЫ.md, записана до расчёта). Сигналы — входы бэктестов журналов: канал, 🇰🇷, 🏦,
🇰🇷🆕, 📢, 🆕 (s20/trades.pkl), 🌊 (s23/final_trades.pkl), 💸 (s21/repay_wide), ↩️ (s21/repay_hold), 🔓 (s28/ul_fidelity.pkl),
🅱️ (s22/h10_ann.pkl). Согласие — сигнал журнала B, если другой журнал дал сигнал по монете в предыдущие W ч; одиночный —
если не дал. По монете — одно событие класса за 48 ч. Сделка — шорт с закрытия первой 15-мин свечи после сигнала
(S_7_20 основной, S_10_15, S_7d), плацебо — та же монета за 45/90/135 сут. Итог — s44/events.pkl.
Запуск из папки с данными: python3 <repo>/research/s44/consensus.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s21", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from oi_test import CUT, DAY, EXITS, PL, cl_t, ct, deal, idx_at  # noqa: E402
from common import K  # noqa: E402

SRC = {"канал": "канал", "🏦": "канал", "↩️": "канал", "💸": "канал", "🆕": "канал", "🇰🇷": "Корея", "🇰🇷🆕": "Корея",
       "🌊": "фандинг", "📢": "объявления", "🅱️": "объявления", "🔓": "объявления"}


def signals():
    rows = []
    T = pd.read_pickle("s20/trades.pkl")
    rows += [(s, float(t), j) for s, t, j in zip(T.s, T.te, T.journal)]
    F = pd.read_pickle("s23/final_trades.pkl")
    F = F[(F.rate <= -0.01) & (F.ih >= 4)]
    rows += [(s, float(t) + 900, "🌊") for s, t in zip(F.s, F["T"])]
    import repay_wide                                                     # 💸 (модуль сам грузит s21/panel.pkl)
    RW = repay_wide.journal(repay_wide.mask())
    rows += [(s, float(t), "💸") for s, t in zip(RW.s, RW["T"])]
    import repay_hold                                                     # ↩️: тейк 10, стоп 25, 48 ч
    RH = repay_hold.journal(repay_hold.signals(), 0.10, 0.25, 48)
    rows += [(s, float(t), "↩️") for s, t in zip(RH.s, RH["T"])]
    U = pd.read_pickle("s28/ul_fidelity.pkl")
    rows += [(s, float(t), "🔓") for s, t in zip(U.s, U.t_in)]
    B = pd.read_pickle("s22/h10_ann.pkl")
    rows += [(s, float(t), "🅱️") for s, t in zip(B.s, B["T"])]
    S = pd.DataFrame(rows, columns=["s", "t", "j"])
    S = S[S.s.isin(list(K))].sort_values("t").reset_index(drop=True)
    return S


def classify(S, W=72):
    """Для каждого сигнала: другие журналы в окне (t − W ч, t]: их число и источники."""
    out = []
    for s, g in S.groupby("s"):
        t, j = g.t.values, g.j.values
        for k in range(len(g)):
            w = (t > t[k] - W * 3600) & (t <= t[k])
            w[k] = False
            others = set(j[w]) - {j[k]}
            out.append(dict(s=s, t=t[k], j=j[k], n_j=len(others) + 1,
                            cross=len({SRC[o] for o in others} - {SRC[j[k]]}) > 0))
    return pd.DataFrame(out).sort_values("t").reset_index(drop=True)


def dedupe(C, gap_h=48):
    keep, last = [], {}
    for r in C.itertuples():
        if r.t - last.get(r.s, -1e18) >= gap_h * 3600:
            keep.append(r.Index); last[r.s] = r.t
    return C.loc[keep]


def trades(C):
    rows = []
    for r in C.itertuples():
        i = idx_at(r.s, r.t)
        if i is None:
            continue
        d = dict(s=r.s, t=r.t, j=r.j, n_j=r.n_j, cross=r.cross)
        for ex in EXITS:
            d[ex] = deal(r.s, i, ex)
            p = [deal(r.s, q, ex) for q in (idx_at(r.s, r.t - dd * DAY) for dd in PL) if q is not None]
            p = [v for v in p if v is not None]
            d["pl_" + ex] = np.mean(p) if p else np.nan
        rows.append(d)
    return pd.DataFrame(rows)


def line(lab, x, col):
    x = x[x[col].notna()]
    if len(x) < 8:
        return f"  {lab:40s} мало ({len(x)})"
    m, t, n = ct(x[col], x.t)
    months = (x.t.max() - x.t.min()) / (30.4 * DAY)
    h1, h2 = x[x.t < CUT][col], x[x.t >= CUT][col]
    dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
    return (f"  {lab:40s} n={n:5d} ({n / months:4.0f}/мес) {m:+7.2%} (t {t:+5.1f}) в плюсе {(x[col] > 0).mean():4.0%} |"
            f" половины {h1.mean():+7.2%} ({len(h1)}) / {h2.mean():+7.2%} ({len(h2)}) | плацебо {x['pl_' + col].mean():+7.2%},"
            f" разница {dp:+6.2%} (t {tp:+4.1f})")


def diff(lab, a, b, col):
    a, b = a[a[col].notna()], b[b[col].notna()]
    x = pd.concat([a.assign(_m=1.0), b.assign(_m=0.0)])
    d, t = cl_t(x[col], x._m, (x.t // DAY).astype(int))
    hh = [a[a.t < CUT][col].mean() - b[b.t < CUT][col].mean(), a[a.t >= CUT][col].mean() - b[b.t >= CUT][col].mean()]
    return f"  {lab:40s} {d:+7.2%} (t {t:+5.1f}) | половины {hh[0]:+7.2%} / {hh[1]:+7.2%}"


def main():
    S = signals()
    print(f"Сигналов {len(S)}: " + ", ".join(f"{k} {v}" for k, v in S.j.value_counts().items()))
    res = {}
    for W in (72, 24, 168):
        C = classify(S, W)
        cons = trades(dedupe(C[C.n_j >= 2]))
        single = trades(dedupe(C[C.n_j == 1]))
        res[W] = (cons, single)
        print(f"\n## Окно {W} ч: согласие {len(cons)} событий, одиночные {len(single)}")
        for ex in EXITS:
            print(line(f"согласие, {ex}", cons, ex))
            print(line(f"одиночные, {ex}", single, ex))
            print(diff(f"согласие − одиночные, {ex}", cons, single, ex))
        if W == 72:
            print("\n  Варианты (окно 72 ч, S_7_20):")
            print(line("три журнала и больше", cons[cons.n_j >= 3], "S_7_20"))
            print(line("разные источники данных", cons[cons.cross], "S_7_20"))
            print(line("один источник", cons[~cons.cross], "S_7_20"))
            print("\n  По журналу второго сигнала (окно 72 ч, S_7_20):")
            for j, x in cons.groupby("j"):
                print(line(f"второй — {j}", x, "S_7_20"))
    pd.to_pickle(res, "s44/events.pkl")


if __name__ == "__main__":
    main()
