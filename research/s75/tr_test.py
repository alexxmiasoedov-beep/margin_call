"""s75 — пик внимания турецкой розницы по полному обороту: пары к лире Binance (s67/try1h.pkl) + BTCTurk (s75/btcturk1h.pkl),
лиры → $ по USDTTRY Binance того же часа (гипотеза — ВЫВОДЫ.md, записана до скачивания BTCTurk). Вход в пятёрку впервые
за 7 сут (s66/attn_test.events: 10 лидеров первой половины и стейблкоины не считаются, фьючерс старше суток); основная
группа — без входов 🔝, 🛒, 🇰🇷 по монете за прошлые 24 ч. Шорт 10/25/48 (основной) и 7 сут со стопом 50%; плацебо —
та же монета за 45/90/135 сут. Запуск из папки с данными."""
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

STABLE = {"USDT", "USDC", "FDUSD", "TUSD", "DAI", "USDE", "USD1", "USDS", "PYUSD", "RLUSD", "BUSD", "EUR", "AEUR", "EURC"}


def panel(binance=True, btcturk=True):
    TR = pickle.load(open("s67/try1h.pkl", "rb"))
    fx = TR["USDTTRY"]; fxs = pd.Series(fx[:, 2], index=fx[:, 0].astype(np.int64) + 3600)
    cols = {}

    def add(c, v):
        if c in STABLE:
            return
        s, _ = fut_of(c)
        if not s:
            return
        usd = (v / fxs.reindex(v.index).ffill()).dropna()
        cols[s] = cols[s].add(usd, fill_value=0.0) if s in cols else usd

    if binance:
        for pair, a in TR.items():
            add(pair[:-3], pd.Series(a[:, 1], index=a[:, 0].astype(np.int64) + 3600))
    if btcturk:
        for pair, a in pickle.load(open("s75/btcturk1h.pkl", "rb")).items():
            add(pair[:-3], pd.Series(a[:, 1], index=a[:, 0].astype(np.int64) + 3600))
    return pd.DataFrame(cols)


def run(V, other, label):
    ev, majors = events(V)
    rows = []
    for s, T in ev:
        i = idx_at(s, T); o = other.get(s, np.zeros(0))
        d = dict(s=s, t=T, past=bool(((o < T) & (o >= T - DAY)).any()))
        for nm, kw in EXITS.items():
            x = trade(s, i, **kw)
            d[nm] = x["net"] if x else np.nan
            p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **kw))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"\n## {label}: фьючерсов {V.shape[1]}; лидеры {majors}\n   событий {len(X)} ({len(X) / months:.1f} в месяц),"
          f" с прошлыми 🔝 🛒 🇰🇷 за 24 ч: {X.past.mean():.0%}")
    for lab, x0 in (("без прошлых 🔝 🛒 🇰🇷", X[~X.past]), ("все события", X)):
        for col in EXITS:
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:20s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")
    return X


def main():
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    other = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        other.setdefault(s, []).append(t)
    other = {s: np.array(v) for s, v in other.items()}
    X = run(panel(), other, "Binance к лире + BTCTurk (основная)")
    X.to_pickle("s75/trades.pkl")
    run(panel(binance=False), other, "только BTCTurk")


if __name__ == "__main__":
    main()
