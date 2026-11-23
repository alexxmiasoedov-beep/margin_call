"""s259, вопрос 4 — каскады по часовым свечам и OI (в монетах): за час цена ±5% (±10%) и OI −5% (−10%) — позиции закрыты
на ходе (вынос шортов на росте, ликвидации лонгов на падении); для сравнения — «набор» (цена ±5%, OI +10%). Частота на 100
монето-суток у перпов без спота против монет со спотом; без спота — полное покрытие (s228/met у 73 перпов), окна событий
(s259/met) и случайная выборка вне окон (s259/met_rand) с весом пул / выборка. Доходы не считаются.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/cascade.py"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import BAR, DAY, MID, OUT, T0, T1, load_k, TMP  # noqa: E402

EDGES = [2.3e6, 5.3e6, 12.4e6, 41.5e6]
TYPES = {"вынос шортов 5/5": (1, 0.05, -0.05), "вынос шортов 10/10": (1, 0.10, -0.10),
         "ликвидации лонгов 5/5": (-1, 0.05, -0.05), "ликвидации лонгов 10/10": (-1, 0.10, -0.10),
         "набор на росте 5/+10": (1, 0.05, 0.10), "набор на падении 5/+10": (-1, 0.05, 0.10)}


def hourly(a):
    t = a["t"].astype(np.int64) + BAR
    m = (t % 3600) == 0
    c = a["c"].astype(float)
    qv = a["qv"].astype(float)
    cq = np.r_[0.0, np.cumsum(qv)]
    j = np.flatnonzero(m)
    j = j[j >= 4]
    H = t[j]
    r = c[j] / c[j - 4] - 1
    q = cq[j + 1] - cq[j - 3]
    ok = (t[j - 4] == H - 3600) & (qv[j] > 0)
    to7 = pd.Series(q).rolling(168, min_periods=24).median().shift(1).values * 24
    return pd.DataFrame({"H": H, "r": r, "q": q, "to7": to7})[ok]


def load_oi(path):
    if not os.path.exists(path):
        return None
    z = np.load(path)
    t, v = (z["t1"], z["v1"]) if "t1" in z.files else (z["t"], z["v"])
    return pd.Series(v[:, 0].astype(float), index=t.astype(np.int64))


def events_for(s, a, u, oi, days=None):
    """Часы с OI в начале и конце часа; признаки типов каскадов. days — ограничение множеством суток (окна/выборка)."""
    h = hourly(a)
    h = h[(h.H > T0) & (h.H <= T1)]
    if days is not None:
        h = h[((h.H - 3600) // DAY * DAY).isin(days)]
    o1 = oi.reindex(h.H.values).values
    o0 = oi.reindex((h.H - 3600).values).values
    h = h.assign(doi=o1 / o0 - 1)
    h = h[np.isfinite(h.doi) & (o0 > 0)]
    s0 = u["spot0"] or np.inf
    h["ns"] = h.H <= s0
    h["s"] = s
    return h


def count(h):
    """Число событий каждого типа (первое за 24 ч у монеты)."""
    out = {}
    for nm, (sg, pr, d) in TYPES.items():
        m = (sg * h.r.values >= pr) & ((h.doi.values <= d) if d < 0 else (h.doi.values >= d))
        x = h[m]
        n, last = 0, {}
        for r in x.itertuples():
            if r.H - last.get(r.s, -1e18) >= DAY:
                n += 1; last[r.s] = r.H
        out[nm] = n
    return out


def main():
    K = load_k()
    U = json.load(open(f"{OUT}/universe.json"))
    met228 = set(f[:-4] for f in os.listdir("s228/met"))
    win = json.load(open(f"{OUT}/met_days.json"))
    R = json.load(open(f"{OUT}/met_rand_days.json")) if os.path.exists(f"{OUT}/met_rand_days.json") else {"pool": 0, "days": {}}
    full, wins, rand = [], [], []
    for s, u in U.items():
        a = K[s]
        if s in met228:
            oi = load_oi(f"s228/met/{s}.npz")
            if oi is not None:
                full.append(events_for(s, a, u, oi))
        else:
            oi = load_oi(f"{OUT}/met/{s}.npz")
            if oi is not None and s in win:
                d = set(int(pd.Timestamp(x, tz="UTC").timestamp()) for x in win[s])
                wins.append(events_for(s, a, u, oi, d))
            oi = load_oi(f"{OUT}/met_rand/{s}.npz")
            if oi is not None and s in R["days"]:
                d = set(int(pd.Timestamp(x, tz="UTC").timestamp()) for x in R["days"][s])
                rand.append(events_for(s, a, u, oi, d))
    F = pd.concat(full, ignore_index=True)
    W = pd.concat(wins, ignore_index=True) if wins else F.iloc[:0]
    Rr = pd.concat(rand, ignore_index=True) if rand else F.iloc[:0]
    for X in (F, W, Rr):
        X["bk"] = np.searchsorted(EDGES, X.to7.fillna(0).values)
    n_samp = sum(len(v) for v in R["days"].values())
    wt = R["pool"] / n_samp if n_samp else 0.0
    print(f"часов с OI: полное покрытие {len(F):,} (без спота {F.ns.sum():,}), окна событий {len(W):,}, выборка {len(Rr):,} "
          f"(вес выборки {wt:.1f})")

    def rate(sel_f, sel_w, sel_r, name):
        f = F[sel_f(F)]; w = W[sel_w(W)]; r = Rr[sel_r(Rr)]
        cf, cw, cr = count(f), count(w), count(r)
        days = len(f) / 24 + len(w) / 24 + len(r) / 24 * wt
        if days < 50:
            return
        print(f"  {name}: монето-суток {days:,.0f} (полное {len(f) / 24:,.0f}, окна {len(w) / 24:,.0f}, выборка {len(r) / 24:,.0f}×{wt:.0f}); "
              + "; ".join(f"{nm} {(cf[nm] + cw[nm] + cr[nm] * wt) / days * 100:.2f}" for nm in TYPES) + " — на 100 монето-суток")

    print("\n### все")
    rate(lambda x: x.ns, lambda x: x.ns, lambda x: x.ns, "без спота")
    rate(lambda x: ~x.ns, lambda x: ~x.ns & False, lambda x: ~x.ns & False, "со спотом")
    for h, (lo, hi) in (("1-я половина", (T0, MID)), ("2-я половина", (MID, T1))):
        sel = lambda x, lo=lo, hi=hi: (x.H >= lo) & (x.H < hi)  # noqa: E731
        rate(lambda x: x.ns & sel(x), lambda x: x.ns & sel(x), lambda x: x.ns & sel(x), f"без спота, {h}")
        rate(lambda x: ~x.ns & sel(x), lambda x: x.ns & False, lambda x: x.ns & False, f"со спотом, {h}")
    print("\n### пятые доли оборота")
    for b in range(5):
        rate(lambda x, b=b: x.ns & (x.bk == b), lambda x, b=b: x.ns & (x.bk == b), lambda x, b=b: x.ns & (x.bk == b), f"без спота, оборот {b + 1}")
        rate(lambda x, b=b: ~x.ns & (x.bk == b), lambda x: x.ns & False, lambda x: x.ns & False, f"со спотом, оборот {b + 1}")
    print("\n### покрытие без спота по источникам (без веса)")
    for nm, X in (("полное (s228)", F[F.ns]), ("окна событий", W[W.ns]), ("выборка вне окон", Rr[Rr.ns])):
        c = count(X)
        print(f"  {nm}: монето-суток {len(X) / 24:,.0f}; " + "; ".join(f"{k} {v}" for k, v in c.items()))
    pd.concat([F.assign(src="full"), W.assign(src="win"), Rr.assign(src="rand")]).to_pickle(f"{TMP}/cascade_hours.pkl")


if __name__ == "__main__":
    main()
