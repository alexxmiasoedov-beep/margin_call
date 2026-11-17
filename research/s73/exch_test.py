"""s73 — пятёрка по обороту на одной корейской бирже (гипотеза — ВЫВОДЫ.md, записана до расчёта). Часовой оборот Upbit и
Bithumb отдельно (s15/kr_candles_<биржа>.pkl, вона → $ по KRW-USDT той же биржи, как в kr_panel.py); для каждой биржи —
вход монеты в пятёрку за 24 ч впервые за 7 сут (s66/attn_test.events: свои 10 лидеров первой половины не считаются,
фьючерс старше суток). Событие — вход на любой из бирж, одно на монету за 7 сут; без событий, где за прошлые 7 сут был
вход 🔝 (s65/trades.pkl). Шорт 10/25/48 (основной) и 7 сут со стопом 50%; плацебо — та же монета за 45/90/135 сут.
Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s66"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import fut_of  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from attn_test import EXITS, events, idx_at, trade  # noqa: E402

STABLE = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "PYUSD", "RLUSD"}


def volumes(ex):
    C = pickle.load(open(f"s15/kr_candles_{ex}.pkl", "rb"))
    u = C["USDT"]; rate = pd.Series(u["c"].astype(float), index=u["t"].astype(np.int64))
    cols = {}
    for b, x in C.items():
        if b in STABLE or not len(x["t"]):
            continue
        s, _ = fut_of(b)
        if not s:
            continue
        t = x["t"].astype(np.int64)
        r = rate.reindex(np.union1d(rate.index, t)).ffill().bfill().reindex(t).values
        v = pd.Series(x["v"].astype(float) / r, index=t + 3600)                       # конец часа
        cols[s] = cols[s].add(v, fill_value=0.0) if s in cols else v
    return pd.DataFrame(cols)


def main():
    S65 = pd.read_pickle("s65/trades.pkl")
    kt = {s: g.t.values for s, g in S65.groupby("s")}
    ev = []
    for ex in ("upbit", "bithumb"):
        e, majors = events(volumes(ex))
        print(f"{ex}: лидеры {majors}; входов в пятёрку {len(e)}")
        ev += [(T, s, ex) for s, T in e]
    ev.sort()
    rows, last = [], {}
    for T, s, ex in ev:
        if T - last.get(s, -1e18) < 7 * DAY:
            continue
        o = kt.get(s, np.zeros(0))
        if ((o <= T) & (o >= T - 7 * DAY)).any():
            continue
        last[s] = T
        i = idx_at(s, T)
        d = dict(s=s, t=T, ex=ex, kt_next=bool(((o > T) & (o <= T + DAY)).any()))
        for nm, kw in EXITS.items():
            x = trade(s, i, **kw)
            d[nm] = x["net"] if x else np.nan
            p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **kw))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s73/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Событий (без 🔝 за 7 сут): {len(X)} ({len(X) / months:.1f} в месяц); после них 🔝 в следующие 24 ч: {X.kt_next.mean():.0%}")
    for lab, x0 in (("обе биржи (основная)", X), ("Upbit", X[X.ex == "upbit"]), ("Bithumb", X[X.ex == "bithumb"])):
        for col in ("S_10_25", "S_7d"):
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:20s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
