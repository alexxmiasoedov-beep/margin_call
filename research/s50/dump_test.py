"""s50 — доля спота Binance в обвале (гипотеза — ВЫВОДЫ.md, записана до расчёта). Обвалы — s7/dumps.pkl (−15% за ≤ 2 ч
из покоя, первый за сутки); доля спота = спот / (спот + фьючерс) за последний полный час до закрытия свечи-триггера.
Трети — по обвалам первой половины. Сделки с закрытия свечи-триггера: лонг и шорт, тейк 10% / стоп 25% / 48 ч; одна
сделка на монету за 48 ч; плацебо — та же монета за 45/90/135 сут. Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402

EX = dict(tp=0.10, sl=0.25, hold_h=48)


def main():
    EV = pickle.load(open("s7/dumps.pkl", "rb"))
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    rows, last = [], {}
    perp_h = {}
    for e in EV:
        s, j, Tp = e["s"], e["jK"], e["t_in"]
        if Tp - last.get(s, -1e18) < 48 * 3600:
            continue
        a = K[s]
        if s not in perp_h:
            Tend = a["t"].astype(np.int64) + 900
            perp_h[s] = pd.Series(a["qv"].astype(float)).groupby(((Tend - 1) // 3600 + 1) * 3600).sum()
        H = (Tp // 3600) * 3600
        sp = SP.get(s); share = np.nan
        if sp is not None:
            m = np.flatnonzero(sp[:, 0].astype(np.int64) == H - 3600)
            v = float(sp[m[0], 1]) if len(m) else np.nan
            pv = float(perp_h[s].get(H, np.nan))
            if v == v and pv == pv:
                share = v / max(v + pv, 1.0)
        d = dict(s=s, t=Tp, spot=sp is not None, share=share)
        ok = True
        for side, nm in ((1, "long"), (-1, "short")):
            x = trade(s, j, side=side, **EX)
            if x is None:
                ok = False; break
            d[nm] = x["net"]
            p = [y["net"] for dd in (45, 90, 135) if j - dd * 96 >= 96 and (y := trade(s, j - dd * 96, side=side, **EX))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        if not ok:
            continue
        last[s] = Tp
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s50/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    h1 = X[(X.t < CUT) & X.share.notna()]
    q1, q2 = h1.share.quantile([1 / 3, 2 / 3])
    print(f"Обвалов со сделкой: {len(X)} за {months:.1f} мес.; со спотом {X.spot.sum()}; трети по первой половине: {q1:.1%} и {q2:.1%}")

    def line(lab, x, col):
        x = x[x[col].notna()]
        if len(x) < 8:
            return f"  {lab:44s} {col:5s} мало ({len(x)})"
        m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
        a, b = x[x.t < CUT][col].mean(), x[x.t >= CUT][col].mean()
        return (f"  {lab:44s} {col:5s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x['pl_' + col].mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    groups = (("все обвалы", X), ("монеты без спота Binance", X[~X.spot]), ("нижняя треть доли спота", X[X.share < q1]),
              ("средняя треть", X[(X.share >= q1) & (X.share < q2)]), ("верхняя треть доли спота", X[X.share >= q2]),
              ("нижняя треть и без спота (Г2)", X[(X.share < q1) | ~X.spot]))
    for lab, x in groups:
        for col in ("long", "short"):
            tag = " ← Г1" if lab.startswith("верхняя") and col == "long" else " ← Г2" if "(Г2)" in lab and col == "short" else ""
            print(line(lab, x, col) + tag)


if __name__ == "__main__":
    main()
