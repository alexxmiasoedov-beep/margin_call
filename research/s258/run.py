"""s258 — «выпавшие из списка»: вчерашние лидеры роста Upbit после сброса дня в 09:00 KST (00:00 UTC). Правило проверки —
ВЫВОДЫ.md, записано до расчёта.

Событие: на 00:00 UTC рост монеты на Upbit за прошедшие сутки Upbit (00:00 → 00:00 UTC, часовые свечи к воне) ≥ 20%, оборот
Upbit за эти сутки ≥ 1 млн $, монета не из постоянных лидеров (KT_MAJORS бота) и не стейблкоин, фьючерс Binance торгуется
≥ суток. Одна сделка на монету за 48 ч. Шорт на закрытии часовой свечи фьючерса в 00:00 UTC; выходы S_10_25 (тейк 10 /
стоп 25 / 48 ч, основной) и S_24h (24 ч, стоп 15%), комиссия 0,1% и фактический фандинг (s88/oos_test.trade1h).
Контроль часа — то же правило в остальные 23 часа (рост за 24 ч до часа ≥ 20%), одна сделка на монету за 48 ч.
Плацебо — та же монета за 45/90/135 сут в тот же час.

Данные: 10.2024–10.2026 — s15/kr_candles_upbit.pkl и 15-мин свечи s2/k2y.pkl (собраны в часовые), фандинг s15/common;
10.2022–09.2024 — s88/oos, 10.2020–09.2022 — s88/oos2020 (fut/, kc/upbit/, map.pkl).
Запуск из /home/user/mc_data: python3 <repo>/research/s258/run.py [count|main]"""
import glob
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
DAY, H1, WEEK, FEE = 86400, 3600, 7 * 86400, 0.001
UP, TURN, GAP = 0.20, 1e6, 48 * 3600
MAJ = {"XRP", "BTC", "ETH", "DOGE", "SOL", "SUI", "ONDO", "ADA", "WLD", "SHIB"}
STABLE = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "USDP", "BUSD", "PYUSD", "RLUSD"}
PER = {"2020–2022": ("s88/oos2020", "2020-10-01", "2022-10-01", "2021-10-01"),
       "2022–2024": ("s88/oos", "2022-10-01", "2024-10-01", "2023-10-01"),
       "2024–2026": (None, "2024-10-01", "2026-10-19", "2025-10-01")}
EXITS = {"S_10_25": dict(tp=0.10, sl=0.25, hold_h=48), "S_24h": dict(tp=None, sl=0.15, hold_h=24)}


def ts(d):
    return int(pd.Timestamp(d, tz="UTC").timestamp())


def trade1h(a, fr, i, tp=None, sl=0.25, hold_h=48, side=-1):
    """Как s88/oos_test.trade1h: вход в закрытии часовой свечи i (t — начало часа)."""
    t = a["t"]; n = int(hold_h)
    if i < 1 or i + n >= len(t) or t[i + n] != t[i] + n * H1:
        return None
    p0 = float(a["c"][i])
    hi, lo, op = (a[x][i + 1:i + n + 1].astype(float) for x in ("h", "l", "o"))
    adv, fav = (hi, lo) if side < 0 else (lo, hi)
    ks = np.flatnonzero(side * (adv - p0 * (1 - side * sl)) <= 0) if sl else np.array([], int)
    kt = np.flatnonzero(side * (fav - p0 * (1 + side * tp)) >= 0) if tp else np.array([], int)
    k_s = int(ks[0]) if len(ks) else n
    k_t = int(kt[0]) if len(kt) else n
    if k_s < n and k_s <= k_t:
        stop = p0 * (1 - side * sl)
        px = (max(stop, op[k_s]) * 1.002) if side < 0 else (min(stop, op[k_s]) * 0.998)
        xi = i + 1 + k_s
    elif k_t < n:
        px, xi = p0 * (1 + side * tp), i + 1 + k_t
    else:
        px, xi = float(a["c"][i + n]), i + n
    t0, t1 = float(t[i]) + H1, float(t[xi]) + H1
    f = float(fr[(fr[:, 0] > t0) & (fr[:, 0] <= t1), 1].sum()) if len(fr) else 0.0
    return side * (px / p0 - 1) - side * f - FEE


def load(per):
    """{монета: (часовые свечи фьючерса, фандинг, свечи Upbit)} и курс вона → доллар по часам."""
    d = PER[per][0]
    out = {}
    if d is None:
        from common import K, fut_of, funding  # noqa: E402
        U = pickle.load(open("s15/kr_candles_upbit.pkl", "rb"))
        usdt = U.get("USDT")
        rate = pd.Series(usdt["c"].astype(float), index=usdt["t"].astype(np.int64))
        for coin, u in U.items():
            sym, _ = fut_of(coin)
            if sym is None or coin in STABLE:
                continue
            k = K[sym]; t15 = k["t"].astype(np.int64)
            g = pd.DataFrame({"h0": t15 // H1 * H1, "o": k["o"], "h": k["h"], "l": k["l"], "c": k["c"], "qv": k["qv"]})
            g = g.groupby("h0").agg(o=("o", "first"), h=("h", "max"), l=("l", "min"), c=("c", "last"), qv=("qv", "sum"),
                                    n=("c", "size"))
            g = g[g.n == 4]
            a = {"t": g.index.values.astype(np.int64), "o": g.o.values, "h": g.h.values, "l": g.l.values, "c": g.c.values,
                 "qv": g.qv.values}
            f0 = funding(sym)
            fr = np.asarray(f0, float).reshape(-1, 2) if len(f0) else np.zeros((0, 2))
            out[coin] = (a, fr, u)
        return out, rate
    mp = pickle.load(open(f"{d}/map.pkl", "rb"))
    F = {os.path.basename(p)[:-4]: x for p in glob.glob(f"{d}/fut/*.pkl") if (x := pickle.load(open(p, "rb")))}
    KC = {}
    for p in glob.glob(f"{d}/kc/upbit/*.pkl"):
        x = pickle.load(open(p, "rb"))
        if x:
            KC[os.path.basename(p)[4:-4]] = x
    btc, kb = F["BTCUSDT"], KC["BTC"]
    rate = (pd.Series(kb["c"], index=kb["t"]) / pd.Series(btc["c"], index=btc["t"])).dropna()
    for coin, sym in mp.items():
        if coin in STABLE or coin not in KC or sym not in F:
            continue
        a = F[sym]
        fr = np.asarray(a["f"], float).reshape(-1, 2) if len(a["f"]) else np.zeros((0, 2))
        out[coin] = (a, fr, KC[coin])
    return out, rate


def events(per, with_trades):
    data, rate = load(per)
    _, a0, a1, _ = PER[per]
    T0, T1 = ts(a0), ts(a1)
    rows = []
    for coin, (a, fr, u) in data.items():
        if coin in MAJ or coin in STABLE:
            continue
        ut = np.asarray(u["t"], np.int64); uc = np.asarray(u["c"], float); uv = np.asarray(u["v"], float)
        s = pd.Series(uc, index=ut)
        v = pd.Series(uv, index=ut)
        r = rate.reindex(np.union1d(rate.index.values, ut)).ffill().bfill().reindex(ut).values
        vusd = pd.Series(uv / np.where(r > 0, r, np.nan), index=ut)
        at = a["t"].astype(np.int64); qv = a["qv"].astype(float)
        live0 = at[np.flatnonzero(qv > 0)[0]] if (qv > 0).any() else np.inf
        # конец часа H (закрытие свечи, начавшейся в H − 1 ч): цена закрытия Upbit
        close_at = pd.Series(uc, index=ut + H1)
        turn24 = vusd.rolling(24, min_periods=24).sum()
        turn24.index = turn24.index + H1                         # оборот 24 свечей, закончившихся в H
        chg = close_at / close_at.shift(24) - 1                  # рост за 24 ч до H (часы подряд)
        ok_seq = pd.Series(close_at.index, index=close_at.index).diff(24) == 24 * H1
        X = pd.DataFrame({"chg": chg, "turn": turn24.reindex(close_at.index)})
        X = X[ok_seq & (X.chg >= UP) & (X.turn >= TURN)]
        X = X[(X.index >= T0) & (X.index < T1) & (X.index >= live0 + DAY)]
        last = {True: -10 ** 12, False: -10 ** 12}
        for H, c24, tv in zip(X.index.values, X.chg.values, X.turn.values):
            o9 = H % DAY == 0
            if H - last[o9] < GAP:
                continue
            i = int(np.searchsorted(at, H - H1))
            if i >= len(at) or at[i] != H - H1 or qv[i] <= 0:
                continue
            rr = dict(coin=coin, t=int(H), o9=o9, chg=float(c24), turn=float(tv))
            if with_trades:
                for nm, kw in EXITS.items():
                    rr[nm] = trade1h(a, fr, i, **kw)
                    pl = []
                    for dd in (45, 90, 135):
                        k = int(np.searchsorted(at, H - H1 - dd * DAY))
                        if k < len(at) and at[k] == H - H1 - dd * DAY and qv[k] > 0:
                            y = trade1h(a, fr, k, **kw)
                            if y is not None:
                                pl.append(y)
                    rr["pl_" + nm] = np.mean(pl) if pl else np.nan
                if rr["S_10_25"] is None:
                    continue
            last[o9] = H
            rows.append(rr)
    X = pd.DataFrame(rows)
    for nm in EXITS:
        if nm in X:
            X[nm] = X[nm].astype(float)
    return X


def wk(t):
    return (np.asarray(t, np.int64) // WEEK) * WEEK


def ct(x, t):
    x = np.asarray(x, float); w = wk(t); ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, m / se if se > 0 else np.nan, len(x)


def diff(y, d, t):
    y = np.asarray(y, float); d = np.asarray(d, float); t = np.asarray(t, float)
    m = ~np.isnan(y); y, d, t = y[m], d[m], t[m]
    Z = np.c_[np.ones(len(y)), d]; A = np.linalg.inv(Z.T @ Z); beta = A @ Z.T @ y; u = y - Z @ beta
    S = pd.DataFrame(Z * u[:, None]).groupby(wk(t)).sum().to_numpy(); G = len(S)
    V = A @ (S.T @ S) @ A * G / (G - 1)
    return float(beta[1]), float(np.sqrt(V[1, 1]))


def months(per):
    _, a, b, _ = PER[per]
    return (ts(b) - ts(a)) / (30.44 * DAY)


def count():
    for per in PER:
        X = events(per, False)
        o = X[X.o9] if len(X) else X
        print(f"{per}: событий 00 UTC {len(o)} ({len(o) / months(per):.1f} в месяц), монет {o.coin.nunique() if len(o) else 0}; "
              f"в другие часы {len(X) - len(o)}")


def line(x, per, col):
    m, t, n = ct(x[col], x.t)
    if n < 5:
        return f"n={n}"
    md, td, _ = ct(x[col] - x["pl_" + col], x.t)
    cut = ts(PER[per][3])
    return (f"n={n} ({n / months(per):.1f} в месяц), {m:+.2%} (t по неделям {t:+.1f}); половины {x[x.t < cut][col].mean():+.2%} / "
            f"{x[x.t >= cut][col].mean():+.2%}; сверх плацебо {md:+.2%} (t {td:+.1f})")


def main():
    parts = []
    for per in PER:
        X = events(per, True)
        X.to_pickle(f"s258_{per}.pkl")
        o, r = X[X.o9], X[~X.o9]
        print(f"== {per}")
        for col in EXITS:
            print(f"  00 UTC, {col}: {line(o, per, col)}")
            print(f"  другие часы, {col}: {line(r, per, col)}")
        d, se = diff(X.S_10_25, X.o9.astype(float), X.t)
        print(f"  Δ (00 UTC − другие часы), S_10_25: {d:+.2%} (t {d / se:+.1f})")
        print(f"  00 UTC, рост ≥ 50%: {line(o[o.chg >= 0.5], per, 'S_10_25')}")
        print(f"  00 UTC, выходные: {line(o[pd.to_datetime(o.t, unit='s').dt.weekday >= 5], per, 'S_10_25')}")
        parts.append((per, o.S_10_25.mean(), d, se, len(X)))
        if per == "2024–2026":
            m, t, n = ct(o.S_10_25, o.t)
            cut = ts(PER[per][3])
            h1, h2 = o[o.t < cut].S_10_25.mean(), o[o.t >= cut].S_10_25.mean()
            md = (o.S_10_25 - o.pl_S_10_25).mean()
            print("  правило владельца: " + "; ".join(f"{k} — {'да' if ok else 'нет'}" for k, ok in
                  (("≥ 20 в месяц", n / months(per) >= 20), ("t ≥ 3", t >= 3), ("обе половины > 0", h1 > 0 and h2 > 0),
                   ("сверх плацебо > 0", md > 0))))
    W = sum(n for *_, n in parts)
    m = sum(d * n for _, _, d, _, n in parts) / W
    se = np.sqrt(sum((s * n) ** 2 for _, _, _, s, n in parts)) / W
    ok = all(om > 0 and d > 0 for _, om, d, _, _ in parts) and m / se >= 2
    print(f"\nТри периода вместе: Δ {m:+.2%} (t {m / se:+.1f})")
    print("порог s258 (в каждом периоде 00 UTC > 0 и Δ > 0, вместе t ≥ 2):", "пройден" if ok else "не пройден")


if __name__ == "__main__":
    {"count": count, "main": main}[sys.argv[1] if len(sys.argv) > 1 else "count"]()
