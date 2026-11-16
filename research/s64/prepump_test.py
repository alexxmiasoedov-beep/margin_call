"""s64 — набор на споте до пампа (гипотеза — ВЫВОДЫ.md, записана до расчёта). Пампы — s15/kr_pumps.pkl у монет со спотом
Binance. H — конец последнего полного часа до закрытия свечи пампа. Доля спота до пампа — по обороту за часы (H − 6 ч,
H − 2 ч]; обычная — медиана часовых долей за 168 ч до этого окна. Отношение — доля до пампа / обычная; трети — по первой
половине. Шорт 10/25/48, одна сделка на монету за 48 ч; плацебо — та же монета за 45/90/135 сут. Пересечение с 🛒 — доля
спота за последний час из s49/trades.pkl. Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402


def main():
    X = pd.read_pickle("s49/trades.pkl")                       # пампы со сделкой: s, t, share (последний час), net, pl
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    X = X[X.s.isin(list(SP))].copy()
    cache, ratio = {}, []
    for r in X.itertuples():
        if r.s not in cache:
            a = K[r.s]; Tend = a["t"].astype(np.int64) + 900
            perp = pd.Series(a["qv"].astype(float)).groupby(((Tend - 1) // 3600 + 1) * 3600).sum()
            sp = SP[r.s]; spv = pd.Series(sp[:, 1], index=sp[:, 0].astype(np.int64) + 3600)
            idx = spv.index.union(perp.index)
            s_, p_ = spv.reindex(idx).fillna(0.0), perp.reindex(idx).fillna(0.0)
            share = (s_ / (s_ + p_).clip(lower=1.0))
            cache[r.s] = (s_, p_, share)
        s_, p_, share = cache[r.s]
        H = (int(r.t) // 3600) * 3600
        w = (s_.index > H - 6 * 3600) & (s_.index <= H - 2 * 3600)
        pre = s_[w].sum() / max(s_[w].sum() + p_[w].sum(), 1.0)
        base = share[(share.index > H - 6 * 3600 - 168 * 3600) & (share.index <= H - 6 * 3600)]
        norm = float(base.median()) if len(base) >= 120 else np.nan
        ratio.append(pre / norm if norm and norm > 0 else np.nan)
    X["ratio"] = ratio
    X = X[X.ratio.notna()]
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    q1, q2 = X[X.t < CUT].ratio.quantile([1 / 3, 2 / 3])
    print(f"Пампов со спотом: {len(X)} ({len(X) / months:.0f} в месяц); трети отношения: {q1:.2f} и {q2:.2f}")

    def line(lab, x):
        if len(x) < 8:
            return f"  {lab:40s} мало ({len(x)})"
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        a, b = x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()
        return (f"  {lab:40s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} |"
                f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x.pl.mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    print(line("нижняя треть", X[X.ratio < q1]))
    print(line("средняя треть", X[(X.ratio >= q1) & (X.ratio < q2)]))
    top = X[X.ratio >= q2]
    print(line("ОСНОВНАЯ: верхняя треть (набор на споте)", top))
    print(line("  без пампов 🛒 (доля за последний час < 25,9%)", top[top.share < 0.259]))


if __name__ == "__main__":
    main()
