"""s84 — пятёрка лидеров роста за день на Upbit или Bithumb (гипотеза — ВЫВОДЫ.md, записана до расчёта). Рост за день на
закрытии часа T — к закрытию последней границы суток биржи до T (Upbit — 00:00 UTC, Bithumb — 15:00 UTC); монеты с фьючерсом
Binance, без лидеров списков (RT_MAJORS бота) и стейблкоинов, оборот на бирже за 24 ч ≥ 1 млн $. Событие — монета в пятёрке
роста биржи, не была в ней 7 сут; фьючерс ≥ суток; одно событие на монету за 7 сут; без входов 🇰🇷, 🛒, 🔝, 👀 (s83) по монете
за прошлые 24 ч. Шорт 10/25/48 (основной) и 7 сут со стопом 50%; плацебо — та же монета за 45/90/135 сут.
Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s66"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
from common import fut_of, live  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from attn_test import EXITS, idx_at, trade  # noqa: E402

BOUND = {"upbit": 0, "bithumb": 15 * 3600}
MAJ = {"upbit": {"XRP", "BTC", "ETH", "DOGE", "SOL", "SUI", "ONDO", "ADA", "SHIB", "XLM"},
       "bithumb": {"XRP", "BTC", "ETH", "DOGE", "SOL", "WLD", "VIRTUAL", "SUI", "PEPE", "ONDO"}}
STABLE = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "PYUSD", "RLUSD", "BUSD", "EUR", "AEUR", "EURI", "USDP"}


def events(ex):
    C = pickle.load(open(f"s15/kr_candles_{ex}.pkl", "rb"))
    u = C["USDT"]; rate = pd.Series(u["c"].astype(float), index=u["t"].astype(np.int64))
    close, vol, sym = {}, {}, {}
    for b, x in C.items():
        if b in STABLE or b in MAJ[ex] or not len(x["t"]):
            continue
        s, _ = fut_of(b)
        if not s:
            continue
        t = x["t"].astype(np.int64)
        r = rate.reindex(np.union1d(rate.index, t)).ffill().bfill().reindex(t).values
        close[b] = pd.Series(x["c"].astype(float), index=t + 3600)
        vol[b] = pd.Series(x["v"].astype(float) / r, index=t + 3600)
        sym[b] = s
    CL, VO = pd.DataFrame(close), pd.DataFrame(vol)
    grid = pd.Index(np.arange(int(pd.Timestamp("2024-10-01", tz="UTC").timestamp()), int(CL.index.max()) + 1, 3600))
    first = CL.apply(lambda c: c.first_valid_index())
    CL = CL.reindex(grid).ffill()
    for b, f in first.items():                                  # до первой сделки рынка цены нет
        CL.loc[CL.index < f, b] = np.nan
    V24 = VO.reindex(grid).fillna(0.0).rolling(24, min_periods=24).sum()
    R = ((grid.values - 1 - BOUND[ex]) // DAY) * DAY + BOUND[ex]
    ref = CL.reindex(R).values
    CH = pd.DataFrame(CL.values / ref - 1, index=grid, columns=CL.columns)
    CH = CH.where(V24 >= 1e6)
    rank = CH.rank(axis=1, ascending=False, method="first")
    top = (rank <= 5) & CH.notna()
    in7 = top.rolling(168, min_periods=1).max().shift(1).fillna(0).astype(bool)
    ev = top & ~in7
    out = []
    for T, row in ev.iterrows():
        for b in row.index[row.values]:
            out.append((int(T), sym[b], ex, float(CH.at[T, b])))
    return out


def main():
    ev = sorted(events("upbit") + events("bithumb"))
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]; S83 = pd.read_pickle("s83/trades.pkl")
    other = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)) + list(zip(S83.s, S83.t)):
        other.setdefault(s, []).append(t)
    other = {s: np.array(v) for s, v in other.items()}
    rows, last = [], {}
    for T, s, ex, ch in ev:
        if T - last.get(s, -1e18) < 7 * DAY:
            continue
        lo, hi = live(s)
        if T < lo + DAY or T > hi:
            continue
        i = idx_at(s, T)
        if i is None:
            continue
        o = other.get(s, np.zeros(0))
        if ((o < T) & (o >= T - DAY)).any():
            continue
        last[s] = T
        d = dict(s=s, t=T, ex=ex, ch=ch)
        for nm, kw in EXITS.items():
            x = trade(s, i, **kw)
            d[nm] = x["net"] if x else np.nan
            p = [y["net"] for dd in (45, 90, 135) if (j := idx_at(s, T - dd * DAY)) is not None and (y := trade(s, j, **kw))]
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s84/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"Входов в пятёрки роста: {len(ev)}; событий после отбора: {len(X)} ({len(X) / months:.1f} в месяц);"
          f" медиана роста за день {X.ch.median():+.0%}; {X.ex.value_counts().to_dict()}")
    for lab, x0 in (("все (основная)", X), ("рост ≥ 30%", X[X.ch >= 0.30]), ("рост < 30%", X[X.ch < 0.30]),
                    ("Upbit", X[X.ex == "upbit"]), ("Bithumb", X[X.ex == "bithumb"])):
        for col in ("S_10_25", "S_7d"):
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:16s} {col:8s} n={n:4d} ({n / months:4.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
