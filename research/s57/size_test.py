"""s57 — мелкие спотовые сделки в пампе (гипотеза — ВЫВОДЫ.md, записана до расчёта). Пампы — s15/kr_pumps.pkl у монет со спотом
Binance, без пампов 🛒 (доля спота < 25,9%) и 🇰🇷 (доля Кореи < 20%). Средний размер спотовой сделки за последний полный
час до закрытия свечи пампа к медиане часовых размеров за прошлые 168 ч. Трети — по первой половине. Шорт 10/25/48,
одна сделка на монету за 48 ч; плацебо — та же монета за 45/90/135 сут. Запуск из папки с данными (после s54)."""
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
    X = pd.read_pickle("s54/trades.pkl")                       # пампы со сделкой, доли спота и Кореи, доход и плацебо
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    X = X[(X.bin_share > 0) & (X.bin_share < 0.259) & (X.kr_share < 0.20) & X.s.isin(list(SP))].copy()
    rel = []
    cache = {}
    for r in X.itertuples():
        if r.s not in cache:
            sp = SP[r.s]; v, n = sp[:, 1].astype(float), sp[:, 3].astype(float)
            size = np.where(n > 0, v / np.maximum(n, 1), np.nan)
            med = pd.Series(size).shift(1).rolling(168, min_periods=120).median().values
            cache[r.s] = (sp[:, 0].astype(np.int64) + 3600, size, med)
        T, size, med = cache[r.s]
        H = (int(r.t) // 3600) * 3600
        k = np.flatnonzero(T == H)
        rel.append(size[k[0]] / med[k[0]] if len(k) and med[k[0]] > 0 else np.nan)
    X["rel"] = rel
    X = X[X.rel.notna()]
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    q1, q2 = X[X.t < CUT].rel.quantile([1 / 3, 2 / 3])
    print(f"Пампов со спотом вне 🛒 и 🇰🇷: {len(X)} ({len(X) / months:.0f} в месяц); трети относительного размера сделки: "
          f"{q1:.2f} и {q2:.2f}")

    def line(lab, x):
        if len(x) < 8:
            return f"  {lab:40s} мало ({len(x)})"
        m, t, n = ct(x.net, x.t); dp, tp, _ = ct(x.net - x.pl, x.t)
        a, b = x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()
        return (f"  {lab:40s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} |"
                f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x.pl.mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")

    print(line("ОСНОВНАЯ: нижняя треть (мелкие сделки)", X[X.rel < q1]))
    print(line("средняя треть", X[(X.rel >= q1) & (X.rel < q2)]))
    print(line("верхняя треть (крупные сделки)", X[X.rel >= q2]))


if __name__ == "__main__":
    main()
