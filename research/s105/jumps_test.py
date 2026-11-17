"""s105 — недельный шорт монет с крупными положительными скачками (гипотеза — ВЫВОДЫ.md, записана до расчёта; Lee & Wang,
JFQA 2025). Каждый понедельник 00:00 UTC: вселенная — фьючерсы с оборотом ≥ 5 млн $ в сутки за неделю отбора, живые обе
недели; PJV — сумма квадратов 15-мин лог-доходностей со скачком вверх (r > 4σ, σ по биполярной вариации); шорт верхнего
дециля на 7 сут, стоп +50% (s15/common.trade). Сравнение — нижний дециль и вся вселенная недели. Запуск из папки с данными
после s103/beta.py: python3 <repo>/research/s105/jumps_test.py"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s103"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from beta import index  # noqa: E402

SKIP = {"BTC", "ETH", "USDC", "FDUSD", "TUSD", "USDP", "DAI", "BUSD", "USDE", "USD1", "PAXG", "XAUT",
        "AAPL", "AMD", "AMZN", "COIN", "CRCL", "GOOGL", "HOOD", "INTC", "META", "MSFT", "MSTR", "MU", "NVDA", "PLTR",
        "QQQ", "SNDK", "SOXL", "SOXS", "SPY", "TSLA", "XAU", "XAG", "XPT", "XPD", "COPPER", "CL", "BZ", "NATGAS",
        "SPCX", "KORU", "SKHYNIX"}
W = 672                                                    # 7 суток 15-мин свечей
JOUR = {"🇰🇷", "🛒", "🔝", "👀", "⏰", "🇹🇷"}


def main():
    tI, I, _, _ = index()
    t = K["BTC"]["t"]; close = t + 900
    syms = [s for s in K if s not in SKIP and len(K[s]["t"]) == len(t)]
    J = pd.read_pickle("s103/beta_trades.pkl"); J = J[J.j.isin(JOUR)]
    jt = {s: g.t.values for s, g in J.groupby("s")}
    first = pd.Timestamp(int(close[0] + 8 * DAY), unit="s").normalize()
    mondays = [d for d in pd.date_range(first, pd.Timestamp(int(close[-1]), unit="s"), freq="W-MON")]
    rows = []
    for M in mondays:
        Mt = int(M.timestamp())
        iM = int(np.searchsorted(close, Mt))
        if iM >= len(t) or close[iM] != Mt or iM + W >= len(t) or iM - W < 1:
            continue
        cand = []
        for s in syms:
            lo, hi = live(s)
            if lo > Mt - 7 * DAY or hi < Mt + 7 * DAY + 900:
                continue
            a = K[s]
            qv = a["qv"][iM - W + 1:iM + 1].astype(np.float64)
            if qv.sum() / 7 < 5e6:
                continue
            c = a["c"][iM - W:iM + 1].astype(np.float64)
            if (c <= 0).any():
                continue
            r = np.diff(np.log(c))
            bv = np.pi / 2 * np.sum(np.abs(r[1:]) * np.abs(r[:-1]))
            sig = np.sqrt(bv / len(r)) if bv > 0 else 0.0
            up = r > 4 * sig if sig > 0 else np.zeros(len(r), bool)
            cand.append((s, float(np.sum(r[up] ** 2)), float(np.sum(r ** 2)), int(up.sum())))
        if len(cand) < 30:
            continue
        D = pd.DataFrame(cand, columns=["s", "pjv", "rv", "nj"]).sort_values(["pjv", "rv"], ascending=False).reset_index(drop=True)
        n = len(D); k = int(np.ceil(n / 10))
        D["dec"] = "mid"; D.loc[:k - 1, "dec"] = "top"; D.loc[n - k:, "dec"] = "bottom"
        mkt = I[min(iM + W, len(I) - 1)] / I[iM] - 1
        for s, pjv, nj, dec in zip(D.s, D.pjv, D.nj, D.dec):
            x = trade(s, iM, tp=None, sl=0.5, hold_h=168, side=-1)
            if not x:
                continue
            tt = jt.get(s, np.zeros(0))
            rows.append(dict(t=float(Mt), s=s, dec=dec, pjv=pjv, nj=nj, net=x["net"], fund=x["fund"], why=x["why"],
                             mkt=mkt, ov=bool(((tt > Mt - 7 * DAY) & (tt <= Mt)).any()), n=n))
    X = pd.DataFrame(rows)
    X.to_pickle("s105/trades.pkl")
    weeks = X.t.nunique(); months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"недель: {weeks}; монет в неделю: медиана {X.groupby('t').size().median():.0f}; "
          f"скачков вверх у верхнего дециля: медиана {X[X.dec == 'top'].nj.median():.0f} за неделю")
    allw = X.groupby("t").net.mean()                               # шорт всей вселенной той же недели
    X["vs"] = X.net - X.t.map(allw)
    for lab, x in (("верхний дециль (основной)", X[X.dec == "top"]), ("верхний без пересечений", X[(X.dec == "top") & ~X.ov]),
                   ("верхний с пересечениями", X[(X.dec == "top") & X.ov]), ("нижний дециль", X[X.dec == "bottom"]),
                   ("вся вселенная", X)):
        m, tt, n = ct(x.net, x.t); dv, tv, _ = ct(x.vs, x.t); hm, th, _ = ct(x.net + x.mkt, x.t)
        h1, h2 = x[x.t < CUT], x[x.t >= CUT]
        print(f"  {lab:27s} n={n:5d} ({n / months:5.1f}/мес) {m:+6.2%} (t {tt:+4.1f}) в плюсе {(x.net > 0).mean():3.0%} "
              f"стопов {(x.why == 'стоп').mean():3.0%} фандинг {x.fund.mean():+6.2%} | половины {ct(h1.net, h1.t)[0]:+6.2%} / "
              f"{ct(h2.net, h2.t)[0]:+6.2%} | к вселенной {dv:+6.2%} (t {tv:+4.1f}) | с хеджем {hm:+6.2%} (t {th:+4.1f})")


if __name__ == "__main__":
    main()
