"""s43 — поиск правил сверх гипотез: только первая половина (события до 01.12.2025, s43/events.pkl из oi_test.py).
Для каждой группы Г1 и признака поста — средний доход по пятым частям признака и разница верхней и нижней пятой части
(t с кластерами по дням). Цели — шорт S_7_20, S_7d и доход к рынку за 24 и 72 ч (знак — в сторону шорта; минус —
в пользу лонга). Вторая половина здесь не используется. Запуск из папки с данными."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oi_test import CUT, DAY, GROUPS, cl_t  # noqa: E402

FEATS = ["oi5m", "oi15m", "oi1h", "oi24h", "p5m", "p15m", "p1h", "p24h", "fund", "vol24", "sig",
         "ls5", "ls1h", "rsi15", "rsi1h"]
TGT = ["S_7_20", "S_7d", "r24", "r72"]


def quint(x, f, col):
    v = x[[f, col, "t"]].dropna()
    if len(v) < 100 or v[f].nunique() < 5:
        return None
    q = pd.qcut(v[f].rank(method="first"), 5, labels=False)
    means = v.groupby(q)[col].mean()
    edges = v.groupby(q)[f].agg(["min", "max"])
    top, bot = q == 4, q == 0
    vv = v[top | bot]
    d, t = cl_t(vv[col], (q[top | bot] == 4).astype(float), (vv.t // DAY).astype(int))
    return means, edges, d, t, len(v)


def main():
    E = pd.read_pickle("s43/events.pkl")
    H1 = E[E.t < CUT]
    print(f"Первая половина: событий {len(H1)} из {len(E)}; по группам {H1.g.value_counts().to_dict()}")
    best = []
    for g, lab in GROUPS.items():
        x = H1[H1.g == g]
        print(f"\n## {lab}: {len(x)} событий (первая половина)")
        for f in FEATS:
            out = []
            for col in TGT:
                r = quint(x, f, col)
                if r is None:
                    continue
                means, edges, d, t, n = r
                out.append(f"{col}: " + " ".join(f"{m:+.1%}" for m in means) + f" | Q5−Q1 {d:+.2%} (t {t:+.1f})")
                best.append((abs(t), g, f, col, d, t, n, edges.iloc[0, 1], edges.iloc[4, 0]))
            if out:
                r = quint(x, f, TGT[0])
                e = r[1] if r else None
                rng = (f" [Q1 ≤ {e.iloc[0, 1]:.4g}, Q5 ≥ {e.iloc[4, 0]:.4g}]" if e is not None else "")
                print(f"  {f}{rng}")
                for o in out:
                    print("     " + o)
    print("\n## Сильнейшие разницы Q5−Q1 на первой половине (|t| ≥ 3)")
    for b in sorted(best, reverse=True):
        if b[0] < 3:
            break
        print(f"  {GROUPS[b[1]][:22]:22s} {b[2]:6s} {b[3]:7s} Q5−Q1 {b[4]:+.2%} (t {b[5]:+.1f}), n={b[6]}, "
              f"Q1 ≤ {b[7]:.4g}, Q5 ≥ {b[8]:.4g}")


if __name__ == "__main__":
    main()
