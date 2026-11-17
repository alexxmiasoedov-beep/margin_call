"""s116 — недельный шорт монет с малой долей в обращении (гипотеза — ВЫВОДЫ.md, записана до расчёта). Доля в обращении =
монеты в обращении CMC на последний день до понедельника (s28/hist/<cid>.json) ÷ полное предложение (s28/unlock_listing.json);
сопоставление CMC → фьючерс — s28/cmc_fetch.tokens, тикер сверяется по цене (0,8–1,25). Каждый понедельник 00:00 UTC —
шорт нижнего дециля на 7 сут, стоп +50% (s15/common.trade); сравнение — верхний дециль и вся вселенная недели.
Запуск из папки с данными после s103/beta.py: python3 <repo>/research/s116/float_test.py"""
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s103", "s28"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from beta import index  # noqa: E402
from cmc_fetch import tokens  # noqa: E402


def mult(s):
    for p, m in (("1000000", 1e6), ("1000", 1e3)):
        if s.startswith(p):
            return m
    return 1.0


def main():
    tI, I, _, _ = index()
    L = {int(x["cryptoId"]): x for x in json.load(open("s28/unlock_listing.json"))}
    H = {}
    for cid, sym, fut in tokens():
        p = f"s28/hist/{cid}.json"
        tot = float(L.get(int(cid), {}).get("totalSupply") or 0)
        if not os.path.exists(p) or tot <= 0 or fut not in K:
            continue
        a = json.load(open(p))
        if not a:
            continue
        H[fut] = (pd.DataFrame(a, columns=["d", "px", "vol", "mcap", "circ"]).assign(
            ts=lambda x: (pd.to_datetime(x.d) - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")).set_index("ts"), tot)
    t0 = K["BTC"]["t"]; close = t0 + 900
    first = pd.Timestamp(int(close[0] + 31 * DAY), unit="s").normalize()
    mondays = [int(d.timestamp()) for d in pd.date_range(first, pd.Timestamp(int(close[-1] - 8 * DAY), unit="s"), freq="W-MON")]
    rows = []
    for Mt in mondays:
        cand = []
        for s, (h, tot) in H.items():
            a = K[s]; cl = a["t"] + 900
            i = int(np.searchsorted(cl, Mt))
            if i + 7 * 96 >= len(cl) or i < 7 * 96 or cl[i] != Mt:
                continue
            lo, hi = live(s)
            if Mt - 30 * DAY < lo or Mt + 7 * DAY + 900 > hi:
                continue
            if a["qv"][i - 7 * 96 + 1:i + 1].astype(float).sum() / 7 < 5e6:
                continue
            hh = h[h.index < Mt]
            if not len(hh) or Mt - hh.index[-1] > 3 * DAY:
                continue
            r = hh.iloc[-1]
            if not (r.circ > 0 and r.px > 0):
                continue
            ratio = float(a["c"][i]) / mult(s) / float(r.px)
            if not (0.8 <= ratio <= 1.25):
                continue
            cand.append((s, i, min(float(r.circ) / tot, 1.0)))
        if len(cand) < 30:
            continue
        D = pd.DataFrame(cand, columns=["s", "i", "fl"]).sort_values("fl").reset_index(drop=True)
        n = len(D); k = int(np.ceil(n / 10))
        D["dec"] = "mid"; D.loc[:k - 1, "dec"] = "low"; D.loc[n - k:, "dec"] = "high"
        j0 = int(np.searchsorted(tI + 900, Mt)); mkt = I[min(j0 + 672, len(I) - 1)] / I[j0] - 1
        for s, i, fl, dec in zip(D.s, D.i, D.fl, D.dec):
            x = trade(s, i, tp=None, sl=0.5, hold_h=168, side=-1)
            if x:
                rows.append(dict(t=float(Mt), s=s, fl=fl, dec=dec, net=x["net"], fund=x["fund"], why=x["why"], mkt=mkt))
    X = pd.DataFrame(rows)
    X.to_pickle("s116/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"недель {X.t.nunique()}, монет во вселенной в неделю медиана {X.groupby('t').size().median():.0f}; доля в обращении "
          f"нижнего дециля медиана {X[X.dec == 'low'].fl.median():.0%}, верхнего {X[X.dec == 'high'].fl.median():.0%}")
    allw = X.groupby("t").net.mean(); X["vs"] = X.net - X.t.map(allw)
    for lab, x in (("нижний дециль (основной)", X[X.dec == "low"]), ("верхний дециль", X[X.dec == "high"]), ("вся вселенная", X)):
        m, tt, n = ct(x.net, x.t); dv, tv, _ = ct(x.vs, x.t); hm, th, _ = ct(x.net + x.mkt, x.t)
        h1, h2 = x[x.t < CUT], x[x.t >= CUT]
        print(f"  {lab:24s} n={n:5d} ({n / months:5.1f}/мес) шорт {m:+6.2%} (t {tt:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} "
              f"фандинг {x.fund.mean():+6.2%} | половины {ct(h1.net, h1.t)[0]:+6.2%} / {ct(h2.net, h2.t)[0]:+6.2%} | "
              f"к вселенной {dv:+6.2%} (t {tv:+4.1f}) | с хеджем {hm:+6.2%} (t {th:+4.1f})")


if __name__ == "__main__":
    main()
