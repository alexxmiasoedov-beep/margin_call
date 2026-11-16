"""s43 — кандидат поиска (выбран на первой половине, oi_explore.py): пост 🔴 (OI за 15 мин упал) при падении цены за 1 ч
(группа dn_dn) и фандинге в посте ≥ +0,01% → лонг монеты с закрытия первой 15-мин свечи после поста, 72 ч, стоп −20%,
без тейка; вариант с хеджем — шорт BTC той же суммы на тот же срок (комиссия 0,1% на ногу). Плацебо — та же монета
за 45/90/135 сут. Аргумент h1 — только первая половина (до 01.12.2025), all — обе. Запуск из папки с данными."""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oi_test import CUT, DAY, K, PL, ct, idx_at, trade  # noqa: E402

FUND_MIN = 0.01
HOLD_H, SL = 72, 0.20


def leg(s, i):
    """Лонг монеты и хедж BTC с закрытия свечи i + 1: (доход лонга, доход хеджа) или None."""
    r = trade(s, i + 1, tp=None, sl=SL, hold_h=HOLD_H, side=1)
    if r is None:
        return None
    b = K["BTC"]["c"]; j0, j1 = i + 1, i + 1 + r["bars"]
    if j1 >= len(b) or not (b[j0] > 0 and b[j1] > 0):
        return None
    return r["net"], -(b[j1] / b[j0] - 1) - 0.001


def evaluate(E):
    rows = []
    for e in E.itertuples():
        i = idx_at(e.s, e.t)
        if i is None:
            continue
        x = leg(e.s, i)
        if x is None:
            continue
        pl, plh = [], []
        for d in PL:
            j = idx_at(e.s, e.t - d * DAY)
            y = leg(e.s, j) if j is not None else None
            if y is not None:
                pl.append(y[0]); plh.append(y[0] + y[1])
        rows.append(dict(s=e.s, t=e.t, long=x[0], hedged=x[0] + x[1], pl=np.mean(pl) if pl else np.nan,
                         plh=np.mean(plh) if plh else np.nan))
    return pd.DataFrame(rows)


def report(X, lab):
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"\n{lab}: сделок {len(X)}, в месяц {len(X) / months:.0f}")
    for col, pcol in (("long", "pl"), ("hedged", "plh")):
        m, t, n = ct(X[col], X.t)
        d, td, _ = ct(X[col] - X[pcol], X.t)
        h1, h2 = X[X.t < CUT][col], X[X.t >= CUT][col]
        print(f"  {col:7s} {m:+.2%} (t {t:+.1f}), в плюсе {(X[col] > 0).mean():.0%} | половины {h1.mean():+.2%} ({len(h1)}) / "
              f"{h2.mean():+.2%} ({len(h2)}) | плацебо {X[pcol].mean():+.2%}, разница с плацебо {d:+.2%} (t {td:+.1f})")


def main(which="h1"):
    E = pd.read_pickle("s43/events.pkl")
    E = E[(E.g == "dn_dn") & (E.fund >= FUND_MIN)]
    if which == "h1":
        E = E[E.t < CUT]
    X = evaluate(E)
    X.to_pickle(f"s43/cand_{which}.pkl")
    report(X, f"Кандидат «🔴 и цена ↓, фандинг ≥ +{FUND_MIN}%» → лонг {HOLD_H} ч, стоп {SL:.0%} ({which})")


if __name__ == "__main__":
    main(*sys.argv[1:])
