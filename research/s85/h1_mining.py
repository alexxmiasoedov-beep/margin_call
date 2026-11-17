"""s85 — отбор условий на первой половине, проверка на второй (протокол — ВЫВОДЫ.md, записан до расчёта). Наборы событий
s69–s84 (кроме ставших журналами) с уже посчитанными доходами; 8 условий × 2 стороны + «без условия»; отбор на первой
половине (≥ 20 сделок в месяц, среднее > 0, t ≥ 3 с кластерами по дням), проверка на второй (t ≥ 2) и критерии владельца
за два года. Запуск из папки с данными."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s76"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, funding, live  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from wk_test import dvol  # noqa: E402

M = 30.4 * DAY


def sets():
    """(название, DataFrame событий с колонками s, t, r — доход, pl — плацебо или NaN)."""
    out = []

    def add(name, X, col, plc=None):
        x = X[X[col].notna()]
        out.append((name, pd.DataFrame({"s": x.s.values, "t": x.t.values.astype(np.int64), "r": x[col].values,
                                        "pl": x[plc].values if plc and plc in x else np.nan})))
    X = pd.read_pickle("s69/trades.pkl"); add("s69 шорт 10/25/48", X, "S_10_25", "pl_S_10_25"); add("s69 шорт 7 сут", X, "S_7d", "pl_S_7d")
    X = pd.read_pickle("s70/trades.pkl"); add("s70 шорт 10/25/48", X, "S_10_25", "pl_S_10_25"); add("s70 шорт 7 сут", X, "S_7d", "pl_S_7d")
    X = pd.read_pickle("s72/trades.pkl")
    L, S = X[X.side > 0], X[X.side < 0]
    add("s72 лонг после ликв. лонгов 24 ч", L, "X_24h", "pl_X_24h"); add("s72 лонг после ликв. лонгов 4 ч", L, "X_4h", "pl_X_4h")
    add("s72 шорт после ликв. шортов 24 ч", S, "X_24h", "pl_X_24h"); add("s72 шорт после ликв. шортов 4 ч", S, "X_4h", "pl_X_4h")
    add("s72 шорт после ликв. шортов 10/25/48", S, "S_10_25", "pl_S_10_25")
    X = pd.read_pickle("s76/trades.pkl")
    for sd, nm in ((-1, "шорт обогнавших"), (1, "лонг отставших")):
        x = X[X.side == sd]; add(f"s76 {nm} 48 ч", x, "n48", "pl"); add(f"s76 {nm} 24 ч", x, "n24")
    X = pd.read_pickle("s77/trades.pkl")
    for sd, nm in ((1, "лонг лидеров"), (-1, "шорт отстающих")):
        x = X[X.side == sd]; add(f"s77 {nm} 48 ч", x, "n48", "pl_n48"); add(f"s77 {nm} 24 ч", x, "n24", "pl_n24")
    X = pd.read_pickle("s78/trades.pkl"); add("s78 шорт 10/25/48", X, "S_10_25", "pl_S_10_25"); add("s78 шорт 7 сут", X, "S_7d", "pl_S_7d")
    X = pd.read_pickle("s79/trades.pkl")
    add("s79 шорт 24 ч", X, "X_24h", "pl_X_24h"); add("s79 шорт 10/25/48", X, "S_10_25", "pl_S_10_25"); add("s79 шорт 72 ч", X, "X_72h", "pl_X_72h")
    X = pd.read_pickle("s80/trades.pkl")
    for sd, nm in (("Long", "ликв. лонгов"), ("Short", "ликв. шортов")):
        x = X[X.side == sd]; add(f"s80 шорт 7 сут через сутки, {nm}", x, "late", "pl_late"); add(f"s80 шорт 7 сут сразу, {nm}", x, "now", "pl_now")
    X = pd.read_pickle("s82/trades.pkl"); add("s82 лонг 10/25/48", X, "L_10_25", "pl_L_10_25"); add("s82 лонг 24 ч", X, "L_24h", "pl_L_24h")
    X = pd.read_pickle("s84/trades.pkl"); add("s84 шорт 10/25/48", X, "S_10_25", "pl_S_10_25"); add("s84 шорт 7 сут", X, "S_7d", "pl_S_7d")
    return out


def features(pairs):
    PU = pickle.load(open("s15/kr_pumps.pkl", "rb"))
    pt = np.sort(np.concatenate([K[s]["t"][v].astype(np.int64) + 900 for s, v in PU.items() if len(v)]))
    bt, bc = K["BTC"]["t"].astype(np.int64) + 900, K["BTC"]["c"].astype(float)
    DV = {}
    F = {}
    for s, t in pairs:
        if s not in K:
            continue
        a = K[s]; tt = a["t"].astype(np.int64) + 900; c = a["c"].astype(float)
        i = np.searchsorted(tt, t, "right") - 1; j = np.searchsorted(tt, t - DAY, "right") - 1
        r24 = c[i] / c[j] - 1 if i >= 0 and j >= 0 and c[j] > 0 else np.nan
        bi = np.searchsorted(bt, t, "right") - 1; bj = np.searchsorted(bt, t - DAY, "right") - 1
        b24 = bc[bi] / bc[bj] - 1 if bi >= 0 and bj >= 0 else np.nan
        fr = funding(s)
        k = np.searchsorted(fr[:, 0], t, "right") - 1 if len(fr) else -1
        f = fr[k, 1] if k >= 0 else np.nan
        if s not in DV:
            DV[s] = dvol(s)
        dv = DV[s]; dd = dv[(dv.index >= t - 31 * DAY) & (dv.index < t - DAY)]
        F[(s, t)] = dict(fz=np.searchsorted(pt, t, "right") - np.searchsorted(pt, t - DAY, "right"), b24=b24, r24=r24, f=f,
                         we=pd.Timestamp(t, unit="s").weekday() >= 5, kr=(t % DAY) < 15 * 3600,
                         young=t - live(s)[0] < 180 * DAY, illiq=(dd.median() < 20e6) if len(dd) else np.nan)
    return F


CONDS = [("без условия", lambda d: np.ones(len(d), bool)),
         ("ажиотаж ≥ 16", lambda d: d.fz >= 16), ("ажиотаж < 16", lambda d: d.fz < 16),
         ("BTC за сутки ≥ 0", lambda d: d.b24 >= 0), ("BTC за сутки < 0", lambda d: d.b24 < 0),
         ("монета за сутки ≥ +10%", lambda d: d.r24 >= 0.10), ("монета за сутки ≤ 0", lambda d: d.r24 <= 0),
         ("фандинг < 0", lambda d: d.f < 0), ("фандинг ≥ 0", lambda d: d.f >= 0),
         ("выходные", lambda d: d.we == True), ("будни", lambda d: d.we == False),  # noqa: E712
         ("корейские часы", lambda d: d.kr == True), ("западные часы", lambda d: d.kr == False),  # noqa: E712
         ("фьючерс < 180 сут", lambda d: d.young == True), ("фьючерс ≥ 180 сут", lambda d: d.young == False),  # noqa: E712
         ("оборот < 20 млн $", lambda d: d.illiq == True), ("оборот ≥ 20 млн $", lambda d: d.illiq == False)]  # noqa: E712


def main():
    S = sets()
    pairs = {(s, int(t)) for _, d in S for s, t in zip(d.s, d.t)}
    F = features(pairs)
    rows = []
    for name, d in S:
        f = pd.DataFrame([F.get((s, int(t)), {}) for s, t in zip(d.s, d.t)], index=d.index)
        d = pd.concat([d, f], axis=1)
        m1 = (CUT - d.t.min()) / M; mall = (d.t.max() - d.t.min()) / M
        for cname, cf in CONDS:
            x = d[np.asarray(cf(d), bool)]
            h1, h2 = x[x.t < CUT], x[x.t >= CUT]
            if len(h1) < 20:
                continue
            a1, t1, n1 = ct(h1.r, h1.t)
            rows.append(dict(set=name, cond=cname, n1m=n1 / m1, m1=a1, t1=t1, sel=(n1 / m1 >= 20 and a1 > 0 and t1 >= 3),
                             x=x, mall=mall))
    R = pd.DataFrame(rows)
    print(f"Кандидатов (набор × условие): {len(R)}; отобрано на первой половине: {R.sel.sum()}")
    print("\nЛучшие по t на первой половине (для понимания, первые 12):")
    for r in R.sort_values("t1", ascending=False).head(12).itertuples():
        print(f"  {r.set:38s} | {r.cond:22s} | {r.n1m:5.1f}/мес {r.m1:+6.2%} (t {r.t1:+4.1f}){'  ← отобран' if r.sel else ''}")
    print("\nПроверка отобранных на второй половине и за два года:")
    for r in R[R.sel].itertuples():
        x = r.x; h2 = x[x.t >= CUT]
        a2, t2, n2 = ct(h2.r, h2.t); a, t, n = ct(x.r, x.t)
        y = x[x.pl.notna()]
        dp, tp, npl = ct(y.r - y.pl, y.t) if len(y) >= 8 else (np.nan, np.nan, 0)
        ok = t2 >= 2 and a2 > 0 and t >= 3 and n / r.mall >= 20 and (np.isnan(tp) or tp >= 2)
        print(f"  {r.set} | {r.cond}: первая {r.m1:+.2%} (t {r.t1:.1f}); вторая {a2:+.2%} (t {t2:.1f}, n {n2});"
              f" два года {a:+.2%} (t {t:.1f}, {n / r.mall:.0f}/мес); сверх плацебо {dp:+.2%} (t {tp:.1f}, n {npl})"
              f" → {'ПОДТВЕРЖДЁН' if ok else 'не подтверждён'}")
    R.drop(columns=["x"]).to_pickle("s85/candidates.pkl")


if __name__ == "__main__":
    main()
