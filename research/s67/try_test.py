"""s67 — пик внимания турецкой розницы (гипотеза — ВЫВОДЫ.md, записана до скачивания). Часовой оборот пар к лире
(s67/try1h.pkl, лиры → $ по USDTTRY того же часа) по фьючерсам Binance; сумма за 24 ч; 10 лидеров первой половины и
стейблкоины не считаются; монета впервые за 7 сут в пятёрке, фьючерс старше суток → шорт 10/25/48 (основной) и 7 сут
со стопом 50%; одна сделка на монету за 7 сут; плацебо — та же монета за 45/90/135 сут; пересечение с 🔝 (s65), 🛒 (s49)
и 🇰🇷 (s20/trades.pkl) в ±24 ч. Запуск из папки с данными."""
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

STABLE = {"USDT", "USDC", "FDUSD", "TUSD", "DAI", "USDE", "USD1", "USDS", "PYUSD", "RLUSD", "BUSD", "EUR", "AEUR"}


def main():
    TR = pickle.load(open("s67/try1h.pkl", "rb"))
    fx = TR["USDTTRY"]; fxs = pd.Series(fx[:, 2], index=fx[:, 0].astype(np.int64) + 3600)
    cols = {}
    for pair, a in TR.items():
        c = pair[:-3]
        if c in STABLE:
            continue
        s, _ = fut_of(c)
        if not s:
            continue
        v = pd.Series(a[:, 1], index=a[:, 0].astype(np.int64) + 3600)
        usd = (v / fxs.reindex(v.index).ffill()).dropna()
        cols[s] = cols[s].add(usd, fill_value=0.0) if s in cols else usd
    V = pd.DataFrame(cols)
    print(f"Фьючерсов с парой к лире: {V.shape[1]}")
    ev, majors = events(V)
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    other = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        other.setdefault(s, []).append(t)
    other = {s: np.array(v) for s, v in other.items()}
    rows = []
    for s, T in ev:
        i = idx_at(s, T)
        d = dict(s=s, t=T, ov=bool((np.abs(other.get(s, np.zeros(0)) - T) <= DAY).any()))
        for nm, kw in EXITS.items():
            x = trade(s, i, **kw)
            d[nm] = x["net"] if x else np.nan
            p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **kw))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s67/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Лидеры: {majors}\nСобытий: {len(X)} ({len(X) / months:.1f} в месяц), с 🔝, 🛒 или 🇰🇷 в ±24 ч: {X.ov.mean():.0%}")
    for lab, x0 in (("все", X), ("без 🔝, 🛒 и 🇰🇷", X[~X.ov])):
        for col in EXITS:
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            a, b = x[x.t < CUT][col].mean(), x[x.t >= CUT][col].mean()
            print(f"  {lab:16s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {a:+6.2%} / {b:+6.2%} | плацебо {x['pl_' + col].mean():+6.2%}, разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
