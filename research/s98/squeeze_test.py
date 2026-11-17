"""s98 — вето сквизов для шорт-журналов: свободный оборот монеты (доля в обращении от общего предложения, CoinMarketCap
s28/hist и s28/unlock_listing.json; день до входа) и ширина роста рынка (доля фьючерсов Binance +5% за 24 ч в момент
входа). Сделки журналов — как в s96 (portfolio.load). Трети признака — внутри каждого журнала; итог — доход минус среднее
журнала. Гипотезы — ВЫВОДЫ.md, записаны до расчёта. Запуск из папки с данными: python3 <путь>/s98/squeeze_test.py"""
import datetime as dt
import glob
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s96"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from portfolio import load  # noqa: E402

H1 = 3600


def cmc_supply():
    """{фьючерс: DataFrame(день → цена, в обращении)}, {фьючерс: общее предложение}."""
    L = json.load(open("s28/unlock_listing.json"))
    sym = {}
    for x in L:
        s, _ = fut_of(str(x.get("symbol", "")).upper())
        if s and s in K and s not in sym and x.get("totalSupply"):
            sym[s] = (x["cryptoId"], float(x["totalSupply"]))
    hist, tot = {}, {}
    for s, (cid, ts) in sym.items():
        f = f"s28/hist/{cid}.json"
        if not os.path.exists(f):
            continue
        rows = json.load(open(f))
        d = pd.DataFrame(rows, columns=["day", "price", "vol", "mcap", "circ"])
        d["day"] = (pd.to_datetime(d.day) - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")   # секунды при любой точности дат
        hist[s] = d.set_index("day").sort_index(); tot[s] = ts
    return hist, tot


def breadth():
    """Часовые ряды: доля фьючерсов с ростом ≥ 5% за 24 ч и рост BTC за 24 ч."""
    hrs = np.arange(1727740800, 1792540800, H1)
    up, n = np.zeros(len(hrs)), np.zeros(len(hrs))
    btc = None
    for s, a in K.items():
        t = a["t"]; c = a["c"].astype(float); qv = a["qv"]
        i = np.searchsorted(t, hrs - 900)                       # свеча, закрывшаяся ровно в час H
        ok = (i < len(t)) & (t[np.minimum(i, len(t) - 1)] == hrs - 900)
        j = np.searchsorted(t, hrs - 900 - 86400)
        ok &= (j < len(t)) & (t[np.minimum(j, len(t) - 1)] == hrs - 900 - 86400)
        ii, jj = np.minimum(i, len(t) - 1), np.minimum(j, len(t) - 1)
        ok &= (qv[ii] > 0) & (qv[jj] > 0)
        r = np.where(ok, c[ii] / c[jj] - 1, np.nan)
        up += np.where(ok, r >= 0.05, 0); n += ok
        if s == "BTC":
            btc = r
    return pd.Series(np.where(n > 50, up / np.maximum(n, 1), np.nan), index=hrs), pd.Series(btc, index=hrs)


def thirds(x, col, lo_bad):
    """Трети признака внутри каждого журнала; плохая треть — нижняя (lo_bad) или верхняя."""
    out = []
    for j, g in x.groupby("j"):
        g = g[g[col].notna()]
        if len(g) < 30:
            continue
        q = pd.qcut(g[col].rank(method="first"), 3, labels=False)
        g = g.assign(q=q.values, rd=g.r - g.r.mean())
        g["bad"] = g.q == (0 if lo_bad else 2)
        out.append(g)
    return pd.concat(out) if out else pd.DataFrame()


def report(lab, G):
    if G.empty:
        print(f"{lab}: мало данных"); return
    b, o = G[G.bad], G[~G.bad]
    mb, tb, nb = ct(b.rd, b.t); mo, to, no = ct(o.rd, o.t)
    d = mb - mo; se = np.hypot(mb / tb if tb else np.nan, mo / to if to else np.nan)
    h = []
    for half in (G.t < CUT, G.t >= CUT):
        x = G[half]; h.append(ct(x[x.bad].rd, x[x.bad].t)[0] - ct(x[~x.bad].rd, x[~x.bad].t)[0])
    sgn = G.groupby("j").apply(lambda g: g[g.bad].r.mean() - g[~g.bad].r.mean())
    stops_b, stops_o = (b.r <= -0.2).mean(), (o.r <= -0.2).mean()
    print(f"{lab}: сделок {len(G)}; плохая треть хуже на {d:+.2%} (t {d / se:+.1f}); половины {h[0]:+.2%} / {h[1]:+.2%};"
          f" журналов с тем же знаком {int((sgn < 0).sum())} из {len(sgn)}; стопов {stops_b:.1%} против {stops_o:.1%}")
    for j, g in G.groupby("j"):
        bb, oo = g[g.bad], g[~g.bad]
        keep = oo.r.sum() >= g.r.sum()
        print(f"   {j:4s} n={len(g):4d}: плохая {bb.r.mean():+6.2%} ({len(bb)}), остальные {oo.r.mean():+6.2%};"
              f" итог журнала {g.r.sum():+6.1f} → без плохой {oo.r.sum():+6.1f}{' (не хуже)' if keep else ''}")


def main():
    X = load()
    hist, tot = cmc_supply()
    fr, fm = [], []
    for s, t in zip(X.s, X.t):
        h = hist.get(s)
        if h is None:
            fr.append(np.nan); fm.append(np.nan); continue
        d = int(t // DAY * DAY) - DAY                            # день до входа
        i = h.index.searchsorted(d, side="right") - 1
        if i < 0 or d - h.index[i] > 3 * DAY:
            fr.append(np.nan); fm.append(np.nan); continue
        row = h.iloc[i]
        fr.append(min(1.0, row.circ / tot[s]) if tot[s] > 0 else np.nan); fm.append(row.circ * row.price)
    X["float"], X["fmcap"] = fr, fm
    B, BTC = breadth()
    hh = (X.t // H1 * H1).astype(np.int64)
    X["breadth"] = B.reindex(hh).values; X["btc24"] = BTC.reindex(hh).values
    X.to_pickle("s98/trades.pkl")
    print(f"Сделок {len(X)}; с данными CMC о свободном обороте {X.float.notna().sum()} ({X.float.notna().mean():.0%});"
          f" ширина роста: медиана {X.breadth.median():.1%}, 90% {X.breadth.quantile(.9):.1%}")
    report("С1 — малая доля в обращении (нижняя треть)", thirds(X, "float", True))
    report("   для отчёта: малая капитализация свободного оборота", thirds(X, "fmcap", True))
    report("С2 — широкий рост рынка (верхняя треть)", thirds(X, "breadth", False))
    report("   для отчёта: рост BTC за 24 ч (верхняя треть)", thirds(X, "btc24", False))


if __name__ == "__main__":
    main()
