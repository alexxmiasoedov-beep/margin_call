"""s179 — круглые уровни цены в долларах (перпы Binance) и в вонах (Upbit, Bithumb): частота событий и контроль той же
формы (некруглые уровни той же густоты), три периода, без доходов и цен после событий.

Запуск: python3 -I probe_round_levels.py <папка данных>

Долларовые события (15 мин, перпы, цена монеты с учётом множителя):
  A. закрытие впервые за 30 сут выше уровня сетки (первое закрытие над уровнем, который 30 сут не пробивался);
  B. первое за 30 сут касание уровня максимумом с закрытием ниже (отказ).
  Сетки: круглая {1, 2, 5}·10^k и {1…9}·10^k; контроль — геометрические середины между соседними уровнями тех же сеток
  ({1,41; 3,16; 7,07}·10^k и {1,41; 2,45; …; 9,49}·10^k) — уровни той же густоты, но не круглые.
Вонные события (часовые закрытия Upbit и Bithumb, только монеты с перпом Binance): A на сетках {1,2,5} и {1…9} вон
и их контроль; оборот рынка к воне за 24 ч ≥ 1 млрд вон. Доля вонных событий, у которых в ±24 ч не было долларового
события A той же сетки, — «чисто корейские» уровни.
Источники вонных свечей: 2024–2026 — s15/kr_candles_{upbit,bithumb}.pkl; 2022–2024 — s88/oos/kc; 2020–2022 — s88/oos2020/kc.
"""
import importlib.util
import os
import pickle
import sys

import numpy as np
import pandas as pd

D = sys.argv[1] if len(sys.argv) > 1 else "/home/user/mc_data"
HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("pcs", os.path.join(HERE, "probe_crowd_signals.py"))
pcs = importlib.util.module_from_spec(spec)
sys.argv = [sys.argv[0], D]
spec.loader.exec_module(pcs)

GRIDS = {"{1,2,5}": (1, 2, 5), "{1…9}": (1, 2, 3, 4, 5, 6, 7, 8, 9)}
CTRL = {"{1,2,5}": (1.4142, 3.1623, 7.0711),
        "{1…9}": tuple(round(float(np.sqrt(k * (k + 1))), 4) for k in range(1, 10))}
KR = {"2020–2022": ("s88/oos2020/kc", "s88/oos2020/map.pkl"), "2022–2024": ("s88/oos/kc", "s88/oos/map.pkl"),
      "2024–2026": ("s15", None)}


def rfloor(p, steps):
    """Наибольший уровень сетки ≤ p; сетка — мантиссы в [1, 10)."""
    p = np.asarray(p, float)
    e = np.floor(np.log10(np.where(p > 0, p, np.nan)))
    m = p / 10 ** e
    st = np.asarray(sorted(steps), float)
    k = np.searchsorted(st, m + 1e-12, side="right") - 1
    lev = np.where(k >= 0, st[np.clip(k, 0, len(st) - 1)] * 10 ** e, st[-1] * 10 ** (e - 1))
    return lev


def usd_events(k, s):
    t = np.asarray(k["t"], np.int64)
    qv = np.asarray(k["qv"], np.float64)
    live = np.flatnonzero(qv > 0)
    if len(live) < 2880 * 2:
        return {}
    a, b = live[0], live[-1] + 1
    t = t[a:b]; qv = qv[a:b]
    mu = pcs.mult(s)
    c = np.asarray(k["c"], np.float64)[a:b] / mu
    h = np.asarray(k["h"], np.float64)[a:b] / mu
    v24 = pd.Series(qv).rolling(96, min_periods=96).sum().values
    W = 2880
    pmax_c = pd.Series(c).shift(1).rolling(W, min_periods=W).max().values
    pmax_h = pd.Series(h).shift(1).rolling(W, min_periods=W).max().values
    ok = v24 >= pcs.VMIN
    ev = {}
    for gname in GRIDS:
        for kind_, steps in (("круглые", GRIDS[gname]), ("контроль", CTRL[gname])):
            rf = rfloor(c, steps)
            ev[f"$ A {gname} {kind_}"] = t[ok & (rf > pmax_c)]
            rh = rfloor(h, steps)
            ev[f"$ B {gname} {kind_}"] = t[ok & (rh > pmax_h) & (c < rh) & (rh > pmax_c)]
    return ev


def kr_series(period):
    """{(биржа, монета): (t, c, v)} часовых свечей к воне."""
    path, mp = KR[period]
    out = {}
    if period == "2024–2026":
        for ex in ("upbit", "bithumb"):
            o = pickle.load(open(os.path.join(D, f"s15/kr_candles_{ex}.pkl"), "rb"))
            for coin, x in o.items():
                out[(ex, coin)] = (np.asarray(x["t"], np.int64), np.asarray(x["c"], float), np.asarray(x["v"], float))
        return out, None
    m = pickle.load(open(os.path.join(D, mp), "rb"))
    for ex in ("upbit", "bithumb"):
        d = os.path.join(D, path, ex)
        for f in os.listdir(d):
            if not f.endswith(".pkl"):
                continue
            x = pickle.load(open(os.path.join(d, f), "rb"))
            coin = f[:-4].replace("KRW-", "").replace("_KRW", "")
            if isinstance(x, dict) and "t" in x and len(x["t"]):
                out[(ex, coin)] = (np.asarray(x["t"], np.int64), np.asarray(x["c"], float), np.asarray(x["v"], float))
    return out, m


def kr_events(t, c, v, t0, t1):
    o = np.argsort(t); t, c, v = t[o], c[o], v[o]
    T = np.arange(t[0] // 3600, t[-1] // 3600 + 1) * 3600
    cc = pd.Series(c, index=t // 3600 * 3600).groupby(level=0).last().reindex(T).ffill().values
    vv = pd.Series(v, index=t // 3600 * 3600).groupby(level=0).sum().reindex(T).fillna(0).values
    v24 = pd.Series(vv).rolling(24, min_periods=24).sum().values
    pmax = pd.Series(cc).shift(1).rolling(720, min_periods=720).max().values
    ok = (v24 >= 1e9) & (T >= t0) & (T < t1)
    ev = {}
    for gname in GRIDS:
        for kind_, steps in (("круглые", GRIDS[gname]), ("контроль", CTRL[gname])):
            rf = rfloor(cc, steps)
            ev[f"₩ A {gname} {kind_}"] = T[ok & (rf > pmax)]
    return ev


def per_month(times, t0, t1):
    months = pd.period_range(pd.Timestamp(t0, unit="s"), pd.Timestamp(t1 - 1, unit="s"), freq="M")
    if not len(times):
        return 0.0, 0.0
    c = pd.Series(pd.to_datetime(np.asarray(times, float), unit="s").to_period("M")).value_counts()
    v = np.array([int(c.get(m, 0)) for m in months])
    return v.mean(), float(np.median(v))


def main():
    for name, path, a, b in pcs.PERIODS:
        t0, t1 = pcs.ts(a), pcs.ts(b)
        with open(os.path.join(D, path), "rb") as f:
            K = pickle.load(f)
        syms = [s for s in K if s not in pcs.BAD and not s.endswith("USDC") and "qv" in K[s]]
        usd = {}
        for s in syms:
            for sig, tl in usd_events(K[s], s).items():
                tl = tl[(tl >= t0) & (tl < t1)]
                usd.setdefault(sig, []).extend((s, int(x)) for x in tl)
        base = {}
        for s in syms:
            for p in ("1000000", "1000", "1M", ""):
                if s.startswith(p) and len(s) > len(p):
                    base.setdefault(s[len(p):], s)
        del K
        print(f"\n##### {name}")
        for sig, lst in usd.items():
            df = pd.DataFrame(lst, columns=["s", "t"])
            df["day"] = df.t // 86400
            df = df.drop_duplicates(["s", "day"])
            m, med = per_month(df.t.values, t0, t1)
            print(f"  {sig:28s} монето-суток {len(df):6d}, в месяц {m:6.1f} (медиана {med:.0f}), монет {df.s.nunique()}")
        kr, mp = kr_series(name)
        usd_A = {g: pd.DataFrame(usd.get(f"$ A {g} круглые", []), columns=["s", "t"]) for g in GRIDS}
        rows = {}
        for (ex, coin), (t, c, v) in kr.items():
            fut = (mp.get(coin) if mp else None)
            fut = fut[:-4] if fut and fut.endswith("USDT") else fut
            if fut is None:
                fut = base.get(coin)
            if fut is None:
                continue
            for sig, tl in kr_events(t, c, v, t0, t1).items():
                rows.setdefault(sig, []).extend((ex, coin, fut, int(x)) for x in tl)
        for sig, lst in rows.items():
            df = pd.DataFrame(lst, columns=["ex", "coin", "fut", "t"])
            df["day"] = df.t // 86400
            both = df.drop_duplicates(["coin", "day"])
            m, med = per_month(both.t.values, t0, t1)
            share = ""
            g = "{1,2,5}" if "{1,2,5}" in sig else "{1…9}"
            if "круглые" in sig and len(usd_A[g]):
                U = usd_A[g]
                near = []
                for _, r in both.iterrows():
                    tt = U.t[U.s == r.fut].values
                    near.append(bool(len(tt)) and bool(np.any(np.abs(tt - r.t) <= 86400)))
                share = f"; без долларового события той же сетки в ±24 ч — {1 - np.mean(near):.0%}"
            per_ex = {e: len(g_.drop_duplicates(['coin', 'day'])) for e, g_ in df.groupby("ex")}
            print(f"  {sig:28s} монето-суток (любая биржа) {len(both):6d}, в месяц {m:6.1f} (медиана {med:.0f}), "
                  f"монет {both.coin.nunique()}, по биржам {per_ex}{share}")


if __name__ == "__main__":
    main()
