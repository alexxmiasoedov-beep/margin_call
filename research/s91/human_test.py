"""s91 — «человеческая» доля пампа (мера — human_fetch.py): шорт на закрытии свечи пампа, тейк 10 / стоп 25 / 48 ч
(основной) и 7 сут со стопом 50%; основная — верхняя треть доли круглых покупок среди пампов основной группы,
сравнение — нижняя треть; плацебо — та же монета за 45/90/135 сут; проверка на номинал — трети внутри третей по цене.
Гипотеза — ВЫВОДЫ.md, записана до загрузки данных. Запуск из папки с данными: python3 <путь>/s91/human_test.py"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, trade  # noqa: E402
from oi_test import CUT, DAY, ct, idx_at  # noqa: E402

EXITS = {"S_10_25": dict(tp=0.10, sl=0.25, hold_h=48), "S_7d": dict(tp=None, sl=0.50, hold_h=168)}


def mult(s):
    return 1e6 if s.startswith(("1000000", "1M")) else (1e3 if s.startswith("1000") else 1.0)


def line(lab, x0, col, months):
    x = x0[x0[col].notna()]
    if len(x) < 8:
        print(f"  {lab:40s} {col:7s} n={len(x)}")
        return None
    m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
    h1, h2 = x[x.t < CUT], x[x.t >= CUT]
    (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
    print(f"  {lab:40s} {col:7s} n={n:5d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
          f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
          f" разница {dp:+6.2%} (t {tp:+4.1f})")
    return m, (abs(m / t) if t else np.nan)


def main():
    H = pickle.load(open("s91/human.pkl", "rb"))
    rows = []
    for (s, j), v in H.items():
        if not isinstance(v, dict) or v["n"] < 100:
            continue
        a = K[s]; T = int(a["t"][j]) + 900
        r = dict(s=s, t=T, price=float(a["c"][j]) / mult(s), **v)
        for nm, kw in EXITS.items():
            y = trade(s, int(j), **kw)
            r[nm] = y["net"] if y else np.nan
            p = [z["net"] for dd in (45, 90, 135) if (k := idx_at(s, T - dd * DAY)) is not None and (z := trade(s, k, **kw))]
            r["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(r)
    X = pd.DataFrame(rows)
    X.to_pickle("s91/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Пампов основной группы с мерой (≥ 100 мелких покупок): {len(X)} ({len(X) / months:.1f} в месяц);"
          f" не посчитано (мало сделок, нет файла): {len(H) - len(X)}")
    print("Доля круглых покупок по объёму: " + ", ".join(f"{k:.0%} — {v:.2%}" for k, v in X.share.quantile([0.1, 1 / 3, 0.5, 2 / 3, 0.9]).items()))
    X["tq"] = pd.qcut(X.share, 3, labels=["нижняя", "средняя", "верхняя"])
    for col in EXITS:
        print(f"\n{col}")
        rt = line("верхняя треть (основная)", X[X.tq == "верхняя"], col, months)
        line("средняя треть", X[X.tq == "средняя"], col, months)
        rb = line("нижняя треть (сравнение)", X[X.tq == "нижняя"], col, months)
        if rt and rb:
            d = rt[0] - rb[0]; se = np.hypot(rt[1], rb[1])
            print(f"  верхняя − нижняя: {d:+6.2%} (t {d / se:+4.1f})")
    print("\nДругие меры (верхняя треть против нижней, S_10_25):")
    for m in ("share_n", "share_q", "share_u"):
        q = pd.qcut(X[m].rank(method="first"), 3, labels=False)
        rt = line(f"{m}: верхняя треть", X[q == 2], "S_10_25", months)
        rb = line(f"{m}: нижняя треть", X[q == 0], "S_10_25", months)
        if rt and rb:
            d = rt[0] - rb[0]; se = np.hypot(rt[1], rb[1])
            print(f"  {m}: верхняя − нижняя: {d:+6.2%} (t {d / se:+4.1f})")
    print("\nПроверка на номинал (трети цены монеты; внутри — трети доли круглых, S_10_25):")
    X["pq"] = pd.qcut(X.price.rank(method="first"), 3, labels=["дешёвые", "средние", "дорогие"])
    for g, x in X.groupby("pq", observed=True):
        q = pd.qcut(x.share.rank(method="first"), 3, labels=False)
        rt = line(f"{g}: верхняя треть доли", x[q == 2], "S_10_25", months)
        rb = line(f"{g}: нижняя треть доли", x[q == 0], "S_10_25", months)
        if rt and rb:
            d = rt[0] - rb[0]; se = np.hypot(rt[1], rb[1])
            print(f"  {g}: верхняя − нижняя: {d:+6.2%} (t {d / se:+4.1f})")


if __name__ == "__main__":
    main()
