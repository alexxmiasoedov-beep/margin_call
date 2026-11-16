"""s28 — чувствительность правила «cliff ≥ 5% или любой ≥ 25%» (шорт T − 7 → T + 1 сут, стоп 50%): день входа
(T − 10 … T − 1), день выхода (T … T + 3), пороги cliff (3–10%) и «любого» разлока (15–40%, без него), стопы, вклад лучших
сделок и монет. Запуск из папки с данными: python3 unlock_sens.py"""
import os
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from unlock_study import CUT, DAY, build, ct, px_ok      # noqa: E402
from unlock_trades import run                            # noqa: E402


def stat(x):
    m, t, n = ct(x.net.values, x.t.values)
    return n, m, t, x[x.t < CUT].net.mean(), x[x.t >= CUT].net.mean()


def line(x, label):
    if not len(x):
        return
    n, m, t, h1, h2 = stat(x)
    print(f"  {label:30s} n={n:4d} {m*100:+6.2f}% (t {t:+4.1f}) медиана {x.net.median()*100:+5.1f}% в плюсе "
          f"{(x.net > 0).mean():.0%} половины {h1*100:+6.2f} / {h2*100:+6.2f}%")


def trades(E, a, b, sl):
    rows = []
    for r in E.itertuples():
        x = run(r.s, r.t + a * DAY, b - a, sl)
        if x:
            rows.append(dict(s=r.s, t=r.t, size=r.size, cliff=r.cliff, **x))
    return pd.DataFrame(rows)


def rule(E, c=5, a=25):
    return E[(E.cliff & (E["size"] >= c)) | (E["size"] >= a)]


if __name__ == "__main__":
    E = build()
    E = E[E["size"] >= 3].copy()
    E = E[[px_ok(r) for r in E.itertuples()]].sort_values("t")
    M = rule(E)
    print(f"событий по правилу: {len(M)}")

    print("\n=== 1. День входа и выхода (правило «cliff ≥ 5% или ≥ 25%», стоп 50%)")
    grid = {}
    for a in (-10, -7, -5, -3, -1):
        for b in (0, 1, 2, 3):
            X = trades(M, a, b, 0.5)
            grid[(a, b)] = stat(X)
            line(X, f"T{a:+d} → T{b:+d}")
    G = pd.DataFrame({k: dict(n=v[0], net=v[1] * 100, t=v[2]) for k, v in grid.items()}).T
    print("\n  чистыми на сделку, %: строки — вход, столбцы — выход")
    print(G.net.unstack().round(2).to_string())
    print("  t:")
    print(G.t.unstack().round(1).to_string())

    print("\n=== 2. Пороги (T − 7 → T + 1, стоп 50%)")
    A = trades(E, -7, 1, 0.5)
    for c in (3, 5, 7, 10):
        for a in (15, 20, 25, 30, 40, 1e9):
            x = A[(A.cliff & (A["size"] >= c)) | (A["size"] >= a)]
            line(x, f"cliff ≥ {c}% или ≥ {a if a < 1e9 else '—'}%")
    line(A[A["size"] >= 25], "только ≥ 25%")
    line(A[A.cliff & (A["size"] >= 5)], "только cliff ≥ 5%")
    line(A[A.cliff & (A["size"] >= 5) & (A["size"] < 25)], "cliff 5–25%")
    line(A[~A.cliff & (A["size"] >= 25)], "без cliff, ≥ 25%")

    print("\n=== 3. Стопы (правило, T − 7 → T + 1)")
    for sl in (None, 0.25, 0.35, 0.5, 0.75, 1.0):
        X = trades(M, -7, 1, sl)
        line(X, f"стоп {'нет' if sl is None else f'{sl:.0%}'}; худшая {X.net.min()*100:+.0f}%, стопов {(X.why == 'стоп').mean():.0%}")

    print("\n=== 4. Вклад лучших сделок и монет (правило, стоп 50%)")
    X = A.merge(M[["s", "t"]], on=["s", "t"])
    line(X, "все")
    for k in (5, 10, 20):
        line(X.drop(X.net.nlargest(k).index), f"без {k} лучших сделок")
    per = X.groupby("s").net.sum().sort_values(ascending=False)
    print(f"  монет {len(per)}; сделок на монету: медиана {X.groupby('s').size().median():.0f}, максимум {X.groupby('s').size().max()}")
    for k in (5, 10):
        line(X[~X.s.isin(per.index[:k])], f"без {k} самых прибыльных монет")
    one = X.sort_values("t").groupby("s").head(1)
    line(one, "только первая сделка каждой монеты")
