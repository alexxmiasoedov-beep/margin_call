"""s264–s266 — общее для проверок гипотез s263 на перпах Binance на акции и фонды США (TRADIFI_PERPETUAL, underlyingType
EQUITY: акции, ETF и плечевые ETF; без Гонконга, Кореи, Китая, сырья, валюты и Pre-IPO).

- Свечи и фандинг — s224/k_d.pkl и s224/fund_d.pkl (по 19.11.2026), сделки — s187/fastbt (логика s15/common.trade без тейка:
  вход в закрытии 15-мин свечи, стоп по худшей из цены стопа и открытия свечи плюс 0,2%, комиссия 0,1% за круг, фактический
  фандинг).
- Время — по Нью-Йорку (zoneinfo), торговые дни — будни без праздников NYSE и сокращённых дней (списки s263/common263).
- Ликвидность — на момент входа: средний оборот перпа за прошлые 7 сут (не меньше суток истории) ≥ 50 млн $ в сутки.
- Плацебо — та же бумага, то же окно по Нью-Йорку 7, 14, 21 и 28 сут назад (тот же день недели), без условия события.
- Хедж (для отчёта) — перп QQQ на то же окно (есть с 06.04.2026).
Запуск — из /home/user/mc_data: python3 -I <repo>/research/s26x/run.py [count|main]."""
import datetime
import json
import os
import sys
from zoneinfo import ZoneInfo

os.environ.setdefault("MC_K", "s224/k_d.pkl")
os.environ.setdefault("MC_F", "s224/fund_d.pkl")
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in ("s187", os.path.join("s263", "study")):
    sys.path.insert(0, os.path.join(HERE, "..", _p))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import fastbt as FB  # noqa: E402
from common263 import ETF, LEV, NYSE_HALF, NYSE_HOLI  # noqa: E402

NY = ZoneInfo("America/New_York")
DAY, BAR, WEEK = 86400, 900, 7 * 86400
D0 = datetime.date(2026, 1, 26)                    # первые акции-перпы (TSLA — 28.01.2026)
D1 = datetime.date(2026, 11, 19)                   # последний день данных k_d
LIQ = 5e7
MONTH = 30.44 * DAY
K = FB.K


def universe():
    EX = json.load(open("s252/exinfo.json"))["symbols"]
    out = {}
    for x in EX:
        if x.get("contractType") == "TRADIFI_PERPETUAL" and x.get("underlyingType") == "EQUITY" and x["symbol"].endswith("USDT"):
            s = x["symbol"][:-4]
            if s in K and (K[s]["qv"] > 0).any():
                out[s] = "LEV" if s in LEV else ("ETF" if s in ETF else "STOCK")
    return out


def trading_days():
    d, out = D0, []
    while d <= D1:
        if d.weekday() < 5 and d.isoformat() not in NYSE_HOLI and d.isoformat() not in NYSE_HALF:
            out.append(d)
        d += datetime.timedelta(1)
    return out


def ts(d, hh, mm):
    """Момент по Нью-Йорку → UTC-секунды."""
    return int(datetime.datetime(d.year, d.month, d.day, hh, mm, tzinfo=NY).timestamp())


class Sym:
    """Свечи символа: индекс свечи по времени закрытия, цена закрытия, оборот за прошлые 7 сут."""

    def __init__(self, s):
        a = K[s]
        self.s = s
        self.t = a["t"].astype(np.int64)
        self.c = a["c"].astype(float)
        qv = a["qv"].astype(float)
        nz = np.flatnonzero(qv > 0)
        self.live0 = int(self.t[nz[0]]) if len(nz) else None
        self.pos = {int(x) + BAR: k for k, x in enumerate(self.t)}
        cs = np.r_[0.0, np.cumsum(qv)]
        n = np.arange(len(qv))
        lo = np.maximum(n - 672, 0)                              # прошлые 7 сут, без текущей свечи
        days = (n - lo) / 96.0
        self.to7 = np.where(days >= 1, (cs[n] - cs[lo]) / np.maximum(days, 1e-9), np.nan)

    def idx(self, T):
        """Индекс свечи, закрывающейся в T (или None)."""
        return self.pos.get(int(T))

    def px(self, T):
        k = self.idx(T)
        return self.c[k] if k is not None else np.nan

    def ok(self, k):
        """Ликвидность и возраст на момент входа (свеча k)."""
        return (k is not None and self.live0 is not None and self.t[k] - self.live0 >= DAY and np.isfinite(self.to7[k])
                and self.to7[k] >= LIQ)


def trades(E, side_col="side", n_bars=None, sl=0.05):
    """E: DataFrame (s, i, x — индекс свечи выхода, side, te, wk_shift-окна для плацебо). Доход — fastbt по сроку n = x − i
    свечей (у всех событий одной гипотезы срок одинаковый). Плацебо — то же окно 7/14/21/28 сут назад."""
    out = []
    Q = Sym("QQQ") if "QQQ" in K else None
    for (s, side), g in E.groupby(["s", side_col]):
        g = g.copy()
        I = g.i.values.astype(np.int64)
        n = int(g.n.iloc[0])
        ok, net, stp, bars, tend = FB.trades(s, I, sl, n / 4.0, int(side))
        g["net"] = np.where(ok, net, np.nan)
        g["stop"] = np.where(ok, stp, False)
        t = K[s]["t"].astype(np.int64)
        if Q is not None:
            qa = np.array([Q.px(int(t[i]) + BAR) for i in I])
            qb = np.array([Q.px(int(x)) for x in np.where(ok, tend, t[I] + BAR)])
            g["hed"] = g.net.values - side * (qb / qa - 1)
        else:
            g["hed"] = np.nan
        acc = np.zeros(len(I)); cnt = np.zeros(len(I))
        for w in (1, 2, 3, 4):
            tt = t[I] - w * WEEK
            j = np.searchsorted(t, tt)
            good = (j < len(t)) & (t[np.minimum(j, len(t) - 1)] == tt)
            jj = np.where(good, j, 0)
            okp, netp, *_ = FB.trades(s, jj, sl, n / 4.0, int(side))
            m = good & okp
            acc[m] += netp[m]; cnt[m] += 1
        g["pl"] = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
        out.append(g)
    X = pd.concat(out, ignore_index=True) if out else E.assign(net=np.nan)
    return X[X.net.notna()].reset_index(drop=True)


def ct(x, t):
    x = np.asarray(x, float); w = (np.asarray(t, np.int64) // WEEK) * WEEK; ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)


def months(X):
    return max((X.te.max() - X.te.min()) / MONTH, 1.0) if len(X) else 1.0


def line(x, mo, mid=None):
    if len(x) < 5:
        return f"n={len(x)}" + (f", среднее {x.net.mean():+.2%}" if len(x) else "")
    m, t, n = ct(x.net, x.te)
    mh, th, nh = ct(x.hed, x.te)
    md, td, _ = ct(x.net - x.pl, x.te)
    s = f"n={n} ({n / mo:.1f} в месяц), {m:+.2%} (t по неделям {t:+.1f})"
    if mid is not None:
        s += f"; половины {x[x.te < mid].net.mean():+.2%} / {x[x.te >= mid].net.mean():+.2%}"
    return (s + f"; с хеджем QQQ {mh:+.2%} (t {th:+.1f}, n={nh}); сверх плацебо {md:+.2%} (t {td:+.1f}), плацебо у "
            f"{x.pl.notna().mean():.0%}; стопов {x.stop.mean():.0%}; дней {x.d.nunique()}")


def verdict(X, name):
    """Правило владельца: ≥ 20 сделок в месяц, t ≥ 3 по неделям, обе половины > 0, сверх плацебо > 0."""
    mo = months(X)
    mid = float(np.median(X.te))
    m, t, n = ct(X.net, X.te)
    h1, h2 = X[X.te < mid].net.mean(), X[X.te >= mid].net.mean()
    md = (X.net - X.pl).mean()
    conds = (("≥ 20 в месяц", n / mo >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
             ("сверх плацебо > 0", md > 0))
    ok = all(c for _, c in conds)
    print(f"\n{name} — порог: " + "; ".join(f"{k} — {'да' if c else 'нет'}" for k, c in conds)
          + f". ИТОГ: {'пройден' if ok else 'не пройден'}")
    return ok


def report(X, name):
    mo = months(X)
    mid = float(np.median(X.te))
    print(f"\n### {name}")
    print(f"всё: {line(X, mo, mid)}")
    print(f"  середина: {pd.Timestamp(mid, unit='s').date()}")
    for g in ("STOCK", "ETF", "LEV"):
        print(f"  {g}: {line(X[X.grp == g], mo)}")
    q = X.mag.quantile([1 / 3, 2 / 3]).values
    print(f"  ход < {q[0]:.1%}: {line(X[X.mag < q[0]], mo)}")
    print(f"  ход ≥ {q[1]:.1%}: {line(X[X.mag >= q[1]], mo)}")
    print("  по месяцам (среднее, сделок):", {k: (round(v.net.mean() * 100, 2), len(v))
                                              for k, v in X.groupby(pd.to_datetime(X.te, unit='s').dt.strftime('%Y-%m'))})
    return verdict(X, name)
