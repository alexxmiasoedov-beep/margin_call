"""s72 — возврат после вынужденных ликвидаций Binance (гипотеза — ВЫВОДЫ.md, записана до расчёта). Посты s72/liq.jsonl
(канал BinanceLiquidations): «#МОНЕТА Liquidated Long|Short: $сумма at $цена». Час H — закрытие часа UTC; L — сумма
ликвидаций одной стороны по монете за час; V — медиана часового оборота фьючерса за 7 сут до H. Событие: L ≥ k·V,
фьючерс торгуется ≥ 30 сут, по монете и стороне одно событие за 24 ч; BTC, ETH и не крипто не берутся. k — наибольший
из 0,25 / 0,5 / 1 / 2 / 4 с ≥ 25 событиями в месяц у каждой стороны на первой половине (выбор только по частоте).
Сделка против потока: лонги ликвидированы → лонг, шорты → шорт; вход на закрытии свечи H … H + 15 мин; основной выход
24 ч, стоп 20%; ещё 4 ч и шорт 10/25/48; плацебо — та же монета в тот же час за 45/90/135 сут.
Запуск из папки с данными; с ключом --counts — только число событий (без доходов)."""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s22"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, fut_of, live, trade  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from common22 import NONCRYPTO  # noqa: E402

H = 3600
PAT = re.compile(r"#(\S+)\s+Liquidated\s+(Long|Short):\s*\$([\d.,]+)\s*([KMB]?)\s+at\s+\$([\d.,]+)")
MULT = {"": 1.0, "K": 1e3, "M": 1e6, "B": 1e9}
KS = (4, 2, 1, 0.5, 0.25)
EXITS = {"X_24h": dict(tp=None, sl=0.20, hold_h=24), "X_4h": dict(tp=None, sl=0.20, hold_h=4)}


def posts():
    rows = []
    for line in open("s72/liq.jsonl"):
        n, ts, txt = json.loads(line)
        m = PAT.search(txt)
        if not m:
            continue
        rows.append((pd.Timestamp(ts).timestamp(), m.group(1).upper(), m.group(2),
                     float(m.group(3).replace(",", "")) * MULT[m.group(4)]))
    X = pd.DataFrame(rows, columns=["t", "coin", "side", "usd"])
    sym = {c: fut_of(c)[0] for c in X.coin.unique()}
    X["s"] = X.coin.map(sym)
    X = X[X.s.notna() & X.s.isin(list(K)) & ~X.s.isin(["BTC", "ETH"]) & ~X.s.isin(list(NONCRYPTO))]
    X["H"] = (np.ceil(X.t / H) * H).astype(np.int64)
    return X


def hourly_qv(s):
    a = K[s]; Tend = a["t"].astype(np.int64) + 900
    return pd.Series(a["qv"].astype(float)).groupby(((Tend - 1) // H + 1) * H).sum()


def entry(s, T):
    t = K[s]["t"]; i = int(np.searchsorted(t, T))
    return i if i < len(t) and t[i] == T else None


def events(P):
    L = P.groupby(["s", "side", "H"]).usd.sum().reset_index()
    out = []
    for s, g in L.groupby("s"):
        q = hourly_qv(s)
        V = q.rolling(168, min_periods=120).median().shift(1)
        lo, hi = live(s)
        for _, r in g.iterrows():
            v = V.get(r.H, np.nan)
            if not v > 0 or r.H < lo + 30 * DAY or r.H + DAY > hi:
                continue
            out.append(dict(s=s, side=r.side, t=int(r.H), L=r.usd, V=v, x=r.usd / v))
    return pd.DataFrame(out).sort_values("t")


def pick(E, k):
    E = E[E.x >= k]; keep, last = [], {}
    for r in E.itertuples():
        if r.t - last.get((r.s, r.side), -1e18) >= DAY:
            last[(r.s, r.side)] = r.t; keep.append(r.Index)
    return E.loc[keep]


def main():
    P = posts()
    print(f"Ликвидаций (без BTC, ETH и не крипто): {len(P)}, монет {P.s.nunique()}, с {pd.Timestamp(P.t.min(), unit='s'):%d.%m.%Y}"
          f" по {pd.Timestamp(P.t.max(), unit='s'):%d.%m.%Y}")
    E = events(P)
    h1m = (CUT - E.t.min()) / (30.4 * DAY)
    k = None
    for kk in KS:
        Z = pick(E, kk); z1 = Z[Z.t < CUT]
        per = z1.groupby("side").size() / h1m
        print(f"  k = {kk}: событий {len(Z)}; на первой половине в месяц — лонги {per.get('Long', 0):.1f}, шорты {per.get('Short', 0):.1f}")
        if k is None and per.get("Long", 0) >= 25 and per.get("Short", 0) >= 25:
            k = kk
    if k is None:                                   # правило не выполнено ни при одном k — наименьший k ряда (см. ВЫВОДЫ)
        k = min(KS)
    print("выбран k =", k)
    if "--counts" in sys.argv:
        return
    Z = pick(E, k)
    btc = hourly_c = None
    bc = pd.Series(K["BTC"]["c"].astype(float), index=K["BTC"]["t"].astype(np.int64) + 900)
    S65 = pd.read_pickle("s65/trades.pkl"); S49 = pd.read_pickle("s49/trades.pkl"); S49 = S49[S49.share >= 0.259]
    S20 = pd.read_pickle("s20/trades.pkl"); S20 = S20[S20.journal == "🇰🇷"]
    other = {}
    for s, t in list(zip(S65.s, S65.t)) + list(zip(S49.s, S49.t)) + list(zip(S20.s, S20.te)):
        other.setdefault(s, []).append(t)
    other = {s: np.array(v) for s, v in other.items()}
    rows = []
    for r in Z.itertuples():
        i = entry(r.s, r.t)
        if i is None:
            continue
        side = 1 if r.side == "Long" else -1
        b0, b1 = bc.get(r.t - H), bc.get(r.t)
        o = other.get(r.s, np.zeros(0))
        d = dict(s=r.s, t=r.t, side=side, x=r.x, L=r.L, btc=abs(b1 / b0 - 1) >= 0.02 if b0 and b1 else False,
                 ov=bool(((o < r.t) & (o >= r.t - DAY)).any()))
        ex = dict(EXITS)
        if side < 0:
            ex["S_10_25"] = dict(tp=0.10, sl=0.25, hold_h=48)
        for nm, kw in ex.items():
            x = trade(r.s, i, side=side, **kw)
            d[nm] = x["net"] if x else np.nan
            p = []
            for dd in (45, 90, 135):
                T2 = r.t - dd * DAY
                j = entry(r.s, T2)
                if j is not None and T2 >= live(r.s)[0] and (y := trade(r.s, j, side=side, **kw)):
                    p.append(y["net"])
            d["pl_" + nm] = np.mean(p) if p else np.nan
        rows.append(d)
    X = pd.DataFrame(rows)
    X.to_pickle("s72/trades.pkl")
    months = (X.t.max() - X.t.min()) / (30.4 * DAY)
    print(f"\nСделок {len(X)} ({len(X) / months:.1f} в месяц); при ходе BTC ≥ 2% за час: {X.btc.mean():.0%};"
          f" с 🛒 🔝 🇰🇷 за 24 ч: {X.ov.mean():.0%}")
    groups = [("обе стороны (основная)", X), ("лонги ликвидированы → лонг", X[X.side > 0]),
              ("шорты ликвидированы → шорт", X[X.side < 0]), ("обе, без хода BTC ≥ 2%", X[~X.btc]),
              ("обе, без 🛒 🔝 🇰🇷", X[~X.ov])]
    for lab, x0 in groups:
        for col in ("X_24h", "X_4h", "S_10_25"):
            if col not in x0:
                continue
            x = x0[x0[col].notna()]
            if len(x) < 8:
                continue
            m, t, n = ct(x[col], x.t); dp, tp, _ = ct(x[col] - x["pl_" + col], x.t)
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            (m1, t1, _), (m2, t2, _) = ct(h1[col], h1.t), ct(h2[col], h2.t)
            print(f"  {lab:28s} {col:7s} n={n:5d} ({n / months:5.1f}/мес) {m:+6.2%} (t {t:+4.1f}) в плюсе {(x[col] > 0).mean():3.0%} |"
                  f" половины {m1:+6.2%} (t {t1:+4.1f}) / {m2:+6.2%} (t {t2:+4.1f}) | плацебо {x['pl_' + col].mean():+6.2%},"
                  f" разница {dp:+6.2%} (t {tp:+4.1f})")


if __name__ == "__main__":
    main()
