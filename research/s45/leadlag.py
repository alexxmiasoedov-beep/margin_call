"""s45 — запаздывание неликвидных альтов за BTC (гипотеза — ВЫВОДЫ.md, записана до проверки). 15-мин свечи s2/k2y.pkl,
все монеты выровнены по сетке BTC. Событие — |r_BTC| ≥ 1% за свечу k (первое в серии, ≥ 1 ч между событиями). У каждой
монеты: β по 15-мин доходам за прошлые 30 сут (≥ 1000 свечей), отставание g = (r − β·r_BTC)·знак r_BTC. Сделка — монета
в сторону BTC, вход по открытию свечи k + 1, выход по закрытию k + h (h = 1, 2, 4), комиссия 0,1%; с хеджем — BTC на β,
ещё 0,1%. Неликвидные — оборот за 24 ч в нижней половине альтов. Контроль — монеты того же события с g > 0.
t — с кластерами по событию. Итог — s45/trades.pkl. Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s22"))
from common22 import NONCRYPTO  # noqa: E402

CUT = pd.Timestamp("2025-12-01", tz="UTC").timestamp()
W, MINOBS, THR, LAG, FEE = 2880, 1000, 0.01, -0.005, 0.001
HS = (1, 2, 4)


def aligned(K):
    b = K["BTC"]; T = b["t"].astype(np.int64); t0 = T[0]; n = len(T)
    A = {}
    for s, a in K.items():
        if s in ("BTC", "ETH") or s in NONCRYPTO or any(s.endswith(x) for x in ("USDC", "FDUSD")):
            continue
        idx = (a["t"].astype(np.int64) - t0) // 900
        ok = (idx >= 0) & (idx < n)
        o = np.full(n, np.nan); c = np.full(n, np.nan); qv = np.zeros(n)
        live = ok & (a["qv"] > 0)
        o[idx[live]] = a["o"][live]; c[idx[live]] = a["c"][live]; qv[idx[live]] = a["qv"][live]
        A[s] = (o, c, qv)
    return T, A


def cl_mean(y, g):
    y = np.asarray(y, float); g = np.asarray(g); m = ~np.isnan(y); y, g = y[m], g[m]
    if len(y) < 10:
        return np.nan, np.nan
    u = pd.Series(y - y.mean()).groupby(g).sum().values; G = len(u)
    se = np.sqrt((u ** 2).sum() * G / (G - 1)) / len(y)
    return y.mean(), y.mean() / se


def cl_diff(a, ga, b, gb):
    y = np.r_[a, b]; x = np.r_[np.ones(len(a)), np.zeros(len(b))]; g = np.r_[ga, gb]
    m = ~np.isnan(y); y, x, g = y[m], x[m], g[m]
    X = np.c_[np.ones_like(x), x]; XtXi = np.linalg.inv(X.T @ X); bb = XtXi @ X.T @ y; u = y - X @ bb
    S = pd.DataFrame(X * u[:, None]).groupby(g).sum().values; G = len(S)
    V = XtXi @ (S.T @ S) @ XtXi * G / (G - 1)
    return bb[1], bb[1] / np.sqrt(V[1, 1])


def main():
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    T, A = aligned(K)
    b = K["BTC"]; ob, cb = b["o"].astype(float), b["c"].astype(float)
    rb = np.r_[np.nan, cb[1:] / cb[:-1] - 1]
    ev, last = [], -10
    for k in np.flatnonzero(np.abs(rb) >= THR):
        if k - last >= 4 and k >= W + 1 and k + 5 < len(T):
            ev.append(k)
        last = k
    ev = np.array(ev)
    months = (T[-1] - T[0]) / (30.4 * 86400)
    print(f"Событий BTC |r| ≥ {THR:.0%} за 15 мин: {len(ev)} ({len(ev) / months:.0f} в месяц); падений {int((rb[ev] < 0).sum())}")
    rows = []
    for s, (o, c, qv) in A.items():
        r = np.r_[np.nan, c[1:] / c[:-1] - 1]
        m = ~np.isnan(r) & ~np.isnan(rb)
        x, y = np.where(m, rb, 0.0), np.where(m, r, 0.0)
        cs = {k: np.r_[0.0, np.cumsum(v)] for k, v in (("n", m.astype(float)), ("x", x), ("y", y), ("xy", x * y), ("xx", x * x))}
        vol = np.r_[0.0, np.cumsum(qv)]
        for k in ev:
            if np.isnan(r[k]) or np.isnan(o[k + 1]):
                continue
            a0, a1 = k - W, k
            n = cs["n"][a1] - cs["n"][a0]
            if n < MINOBS:
                continue
            Sx, Sy, Sxy, Sxx = (cs[q][a1] - cs[q][a0] for q in ("x", "y", "xy", "xx"))
            den = n * Sxx - Sx ** 2
            if den <= 0:
                continue
            beta = (n * Sxy - Sx * Sy) / den
            side = np.sign(rb[k])
            g = (r[k] - beta * rb[k]) * side
            d = dict(s=s, k=int(k), t=float(T[k]) + 900, side=side, beta=beta, g=g, vol24=vol[k + 1] - vol[k - 95],
                     stale=side * (r[k]))
            for h in HS:
                if np.isnan(c[k + h]):
                    d[f"n{h}"] = d[f"h{h}"] = np.nan
                    continue
                ra = c[k + h] / o[k + 1] - 1; rbb = cb[k + h] / ob[k + 1] - 1
                d[f"n{h}"] = side * ra - FEE
                d[f"h{h}"] = side * (ra - beta * rbb) - 2 * FEE
                d[f"c{h}"] = side * (c[k + h] / c[k] - 1) - FEE        # вход по закрытию свечи события (устаревшая цена)
            rows.append(d)
    X = pd.DataFrame(rows)
    X["illiq"] = X.groupby("k").vol24.transform(lambda v: v <= v.median())
    X.to_pickle("s45/trades.pkl")
    print(f"Монето-событий {len(X)}; с отставанием (g ≤ {LAG:.1%}): {(X.g <= LAG).sum()}, без (g > 0): {(X.g > 0).sum()}")
    for liq, lab in ((True, "неликвидные"), (False, "ликвидные")):
        lag = X[(X.illiq == liq) & (X.g <= LAG)]; ctl = X[(X.illiq == liq) & (X.g > 0)]
        mo = len(lag) / months
        print(f"\n## {lab}: отстающих {len(lag)} ({mo:.0f} в месяц), контроль {len(ctl)}")
        for h in HS:
            for col, nm in ((f"n{h}", "без хеджа"), (f"h{h}", "с хеджем BTC"), (f"c{h}", "вход по закрытию события")):
                mm, t = cl_mean(lag[col], lag.k)
                h1, h2 = lag[lag.t < CUT][col].mean(), lag[lag.t >= CUT][col].mean()
                cm = ctl[col].mean()
                d, td = cl_diff(lag[col].values, lag.k.values, ctl[col].values, ctl.k.values)
                print(f"  выход k+{h} ({15 * h} мин), {nm:24s}: {mm:+.3%} (t {t:+.1f}) | половины {h1:+.3%} / {h2:+.3%} |"
                      f" контроль {cm:+.3%}, разница {d:+.3%} (t {td:+.1f}) | в плюсе {(lag[col] > 0).mean():.0%}")


if __name__ == "__main__":
    main()
