"""s111 — лонг токенов с растущими комиссиями протокола (протокол — ВЫВОДЫ.md). Шаг 1 (по умолчанию): только первая
половина — децили мер роста комиссий и выручки (acc, g30, div) внутри недели, доход лонга за 7 сут (цена − 0,1%
+ полученный фандинг) абсолютный и сверх средней монеты вселенной. Шаг 2 (--rule): правило из ВЫВОДЫ.md на всей
истории. Запуск из папки с данными после llama_fetch.py: python3 <repo>/research/s111/fees_test.py [--rule]"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s105"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, funding, live  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from jumps_test import SKIP  # noqa: E402


def series(slugs, dt):
    tot = None
    for slug in slugs:
        p = f"s111/llama/{slug}_{dt}.json"
        if not os.path.exists(p):
            continue
        a = json.load(open(p))
        if not a:
            continue
        s = pd.Series({int(x[0]) // DAY * DAY: float(x[1] or 0) for x in a})
        tot = s if tot is None else tot.add(s, fill_value=0)
    return tot.sort_index() if tot is not None else None


def panel():
    M = json.load(open("s111/map.json"))
    t = K["BTC"]["t"]; close = t + 900
    first = pd.Timestamp(int(close[0] + 40 * DAY), unit="s").normalize()
    mondays = [int(d.timestamp()) for d in pd.date_range(first, pd.Timestamp(int(close[-1] - 8 * DAY), unit="s"), freq="W-MON")]
    rows = []
    for s, slugs in M.items():
        if s in SKIP or s not in K:
            continue
        fe, rv = series(slugs, "dailyFees"), series(slugs, "dailyRevenue")
        if fe is None or len(fe) < 60:
            continue
        a = K[s]; c = a["c"].astype(float); qv = a["qv"].astype(float)
        lo, hi = live(s); fr = funding(s)
        cl = a["t"] + 900
        for Mt in mondays:
            i = int(np.searchsorted(cl, Mt))
            if i + 7 * 96 >= len(cl) or i < 30 * 96 or cl[i] != Mt or Mt - 30 * DAY < lo or Mt + 7 * DAY > hi:
                continue
            if qv[i - 7 * 96 + 1:i + 1].sum() / 7 < 5e6:
                continue
            d = dict(s=s, t=float(Mt))
            for nm, ser in (("f", fe), ("r", rv)):
                if ser is None:
                    continue
                w = ser[(ser.index < Mt) & (ser.index >= Mt - 60 * DAY)]
                if len(w) < 55:
                    continue
                v = lambda a_, b_: float(w[(w.index >= Mt - a_ * DAY) & (w.index < Mt - b_ * DAY)].sum())
                f7, f28, f30, f30p = v(7, 0), v(35, 7), v(30, 0), v(60, 30)
                if nm == "f" and f30 < 1e5:
                    break
                d[f"{nm}acc"] = f7 / (f28 / 4) - 1 if f28 > 0 else np.nan
                d[f"{nm}g30"] = f30 / f30p - 1 if f30p > 0 else np.nan
                r30 = c[i] / c[i - 30 * 96] - 1
                d[f"{nm}div"] = np.log1p(d[f"{nm}g30"]) - np.log1p(r30) if f30p > 0 and d[f"{nm}g30"] > -1 else np.nan
            else:
                fsum = float(fr[(fr[:, 0] > Mt) & (fr[:, 0] <= Mt + 7 * DAY), 1].sum()) if len(fr) else 0.0
                d["L7"] = c[i + 7 * 96] / c[i] - 1 - 0.001 - fsum
                d["i"] = i
                rows.append(d)
    X = pd.DataFrame(rows)
    X["x7"] = X.L7 - X.groupby("t").L7.transform("mean")
    return X


def step1(X):
    F = X[X.t + 7 * DAY < CUT]
    print(f"первая половина: строк {len(F)}, монет {F.s.nunique()}, недель {F.t.nunique()}, монет в неделю медиана "
          f"{F.groupby('t').size().median():.0f}; средний лонг {F.L7.mean():+.2%}")
    for col in ("facc", "fg30", "fdiv", "racc", "rg30", "rdiv"):
        if col not in F:
            continue
        x = F[F[col].notna()].copy()
        x["q"] = np.minimum((x.groupby("t")[col].rank(pct=True, method="first") * 5).astype(int), 4)
        cells = []
        for k in range(5):
            y = x[x.q == k]
            m, tt, _ = ct(y.L7, y.t); mx, tx, _ = ct(y.x7, y.t)
            cells.append(f"{m:+5.1%}({tt:+.1f}) сверх {mx:+5.1%}({tx:+.1f})")
        print(f"  {col:5s} n={len(x):5d} | " + " | ".join(cells))


if __name__ == "__main__":
    X = panel()
    X.to_pickle("s111/panel.pkl")
    if "--rule" not in sys.argv:
        step1(X)
