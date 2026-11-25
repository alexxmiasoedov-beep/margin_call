"""s291 — подготовка входов журналов внимания (без доходов): одновременность событий (Г2 s290) и расстояние до
365-дневного максимума (Г3 s290). Доходы здесь не читаются — только время, монета и признаки.

Входы (уже посчитанные сделки 8 ч и 24 ч со стопом 10%): ⏰, 🇰🇷, 👀 — s277; 🔝 — s285; 🛒 — s270 (группа S, шорт).
Признаки:
  C   — число других криптоперпов (возраст ≥ 30 сут), выросших за 2 ч до входа на ≥ 10% (одновременные события);
  d365 — цена входа к максимуму дневных максимумов за дни [D − 366, D − 2] (без текущих и вчерашних суток);
  age365 — у монеты есть свечи с оборотом не позже чем за 365 сут до входа.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s291/prep.py → /home/user/mc_data/s291_entries.pkl"""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s259", "study"))
from common259 import crypto_perps  # noqa: E402

BAR, DAY = 900, 86400
D0 = "/home/user/mc_data"
KF = {"2019–2020": "s192/k_2019.pkl", "2020–2022": "s117/k_2020.pkl", "2022–2024": "s117/k_oos.pkl",
      "2024–2026": "s2/k2y.pkl"}
PERS = ("2020–2022", "2022–2024", "2024–2026")


def entries():
    rows = []
    for p in PERS:
        a = pd.read_pickle(f"{D0}/s277_{p}.pkl")
        a = a[a.h.isin(["⏰", "🇰🇷", "👀"]) & a.ex.isin(["8 ч", "24 ч"])][["h", "ex", "s", "te"]]
        b = pd.read_pickle(f"{D0}/s285_{p}.pkl")
        b = b[b.ex.isin(["8 ч", "24 ч"])][["ex", "s", "te"]].assign(h="🔝")
        c = pd.read_pickle(f"{D0}/s270_{p}.pkl")
        c = c[(c.grp == "S") & (c.side == -1) & (c.sl == 0.10) & c.hold.isin([8, 24])][["s", "te", "hold"]]
        c = c.assign(h="🛒", ex=c.hold.map({8: "8 ч", 24: "24 ч"})).drop(columns="hold")
        x = pd.concat([a, b, c], ignore_index=True)
        x["per"] = p
        rows.append(x)
    X = pd.concat(rows, ignore_index=True)
    X["te"] = X.te.astype(np.int64)
    return X


def daily_highs():
    """Дневные максимумы по всем четырём файлам свечей (только свечи с оборотом)."""
    H = {}
    for name, f in KF.items():
        K = pickle.load(open(f"{D0}/{f}", "rb"))
        for s, a in K.items():
            t = np.asarray(a["t"], np.int64)
            ok = np.asarray(a["qv"]) > 0
            if not ok.any():
                continue
            d = t[ok] // DAY
            h = pd.Series(np.asarray(a["h"], float)[ok]).groupby(d).max()
            H[s] = h if s not in H else pd.concat([H[s], h]).groupby(level=0).max()
        del K
        print("максимумы", name, len(H), flush=True)
    return H


def concurrency(X):
    """C — число других криптоперпов с ростом ≥ 10% за 2 ч до входа (по свечам периода входа)."""
    X["C"] = np.nan
    X["px"] = np.nan
    for p in PERS:
        K = pickle.load(open(f"{D0}/{KF[p]}", "rb"))
        coins = [c for c in crypto_perps(K) if c in K]
        t0 = min(int(np.asarray(K[c]["t"])[0]) for c in coins)
        t1 = max(int(np.asarray(K[c]["t"])[-1]) for c in coins) + BAR
        n = (t1 - t0) // BAR
        C = np.full((len(coins), n), np.nan, np.float32)
        first = np.full(len(coins), np.inf)
        for j, c in enumerate(coins):
            a = K[c]
            tt = np.asarray(a["t"], np.int64)
            ok = np.asarray(a["qv"]) > 0
            C[j, (tt[ok] - t0) // BAR] = np.asarray(a["c"])[ok]
            if ok.any():
                first[j] = tt[ok][0]
        C = pd.DataFrame(C.T).ffill(limit=16).to_numpy(np.float32).T
        idx = {c: j for j, c in enumerate(coins)}
        m = X.per == p
        for k in np.flatnonzero(m.values):
            te, s = int(X.te.iat[k]), X.s.iat[k]
            i = (te - BAR - t0) // BAR                       # свеча входа (открыта в te − 15 мин)
            if i - 8 < 0 or i >= n:
                continue
            with np.errstate(invalid="ignore", divide="ignore"):
                r = C[:, i] / C[:, i - 8] - 1
            live = first <= te - 30 * DAY
            if s in idx:
                live[idx[s]] = False
                X.iat[k, X.columns.get_loc("px")] = C[idx[s], i]
            X.iat[k, X.columns.get_loc("C")] = int(np.sum((r >= 0.10) & live))
        del K, C
        print("одновременность", p, int(m.sum()), flush=True)
    return X


def distance(X, H):
    X["d365"] = np.nan
    X["age365"] = False
    for k in range(len(X)):
        s, te, px = X.s.iat[k], int(X.te.iat[k]), X.px.iat[k]
        h = H.get(s)
        if h is None or not np.isfinite(px):
            continue
        D = te // DAY
        X.iat[k, X.columns.get_loc("age365")] = bool(h.index.min() <= D - 365)
        w = h[(h.index >= D - 366) & (h.index <= D - 2)]
        if len(w):
            X.iat[k, X.columns.get_loc("d365")] = px / w.max() - 1
    return X


if __name__ == "__main__":
    X = entries()
    print("входов", X.groupby(["per", "h", "ex"]).size().unstack("ex").to_string(), flush=True)
    X = concurrency(X)
    X = distance(X, daily_highs())
    X.to_pickle(f"{D0}/s291_entries.pkl")
    x = X[X.ex == "8 ч"]
    print("\nC (одновременные события) — квантили по периодам:")
    print(x.groupby("per").C.describe(percentiles=[1 / 3, 0.5, 2 / 3, 0.9]).round(1).to_string())
    print("\nd365 — группы (возраст ≥ 365 сут):")
    g = pd.cut(x.d365, [-np.inf, -0.5, 0, np.inf], right=False, labels=["≤ −50%", "−50…0%", "≥ 0 (новый максимум)"])
    print(pd.crosstab([x.per, x.h], [x.age365, g]).to_string())
