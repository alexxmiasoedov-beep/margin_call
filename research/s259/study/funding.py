"""s259, вопрос 2 — фандинг перпов без спота против монет со спотом: распределение ставки (за начисление и в пересчёте на 8 ч),
крайние начисления (≤ −0,5%, ≥ +0,5%), интервал начисления (переводы на 1–4 ч), кто платит, длительность эпизодов крайнего
фандинга, потолки ставки (снимок fundingInfo). Доходы не считаются.
Фандинг — s2/fund2y.pkl (по 30.09.2026) и кэш s15/fund (09–10.2026); «без спота на момент» — по s259/universe.json.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s259/study/funding.py"""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import DAY, MID, OUT, T0, T1, TMP  # noqa: E402

SNAP0 = int(pd.Timestamp("2026-07-01", tz="UTC").timestamp())


def load():
    F = pickle.load(open("s2/fund2y.pkl", "rb"))
    U = json.load(open(f"{OUT}/universe.json"))
    rows = []
    for s, u in U.items():
        f = F.get(s)
        r = [(int(round(x[0] / 60.0)) * 60, float(x[1]), float(x[2])) for x in f] if f is not None else []
        last = max((x[0] for x in r), default=0)
        for m in ("2026-09", "2026-10"):
            path = f"s15/fund/{s}-{m}.csv"
            if os.path.exists(path):
                for ln in open(path).read().splitlines():
                    p = ln.split(",")
                    if p and p[0].isdigit() and int(p[0]) // 1000 > last + 60:
                        r.append((int(p[0]) // 1000 // 60 * 60, float(p[1]), float(p[2])))
        if not r:
            continue
        a = pd.DataFrame(r, columns=["t", "h", "r"]).drop_duplicates("t").sort_values("t")
        a = a[(a.t >= max(T0, u["live0"])) & (a.t < min(T1, u["live1"] + 900))]
        if not len(a):
            continue
        a["s"] = s
        s0 = u["spot0"] or np.inf
        a["ns"] = a.t < s0
        a["snap"] = u["snap"]; a["self"] = u.get("self", np.nan); a["alpha"] = u.get("alpha", np.nan)
        a["spot0"] = u["spot0"] or np.nan
        rows.append(a)
    D = pd.concat(rows, ignore_index=True)
    D["r8"] = D.r * 8 / D.h
    return D


def turnover(D):
    """Оборот перпа за 7 сут до начисления ($/сут) — для сравнения при равном обороте."""
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    out = np.full(len(D), np.nan)
    for s, g in D.groupby("s"):
        a = K[s]; t = a["t"].astype(np.int64) + 900
        cs = np.r_[0.0, np.cumsum(a["qv"].astype(float))]
        i = np.searchsorted(t, g.t.values, side="right")            # свечей, закрытых к моменту начисления
        lo = np.maximum(i - 672, 0)
        out[g.index] = (cs[i] - cs[lo]) / np.maximum(i - lo, 1) * 96
    return out


def episodes(g, cond):
    """Подряд идущие начисления с условием: длительность в часах (сумма интервалов) и число начислений."""
    x = cond.values.astype(int)
    d = np.diff(np.r_[0, x, 0]); st, en = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    h = g.h.values
    return [(int(g.t.values[a]), float(h[a:b].sum()), b - a) for a, b in zip(st, en)]


def describe(D, name):
    if not len(D):
        print(f"\n== {name}: нет данных"); return
    days = 0.0
    for s, g in D.groupby("s"):
        days += (g.t.max() - g.t.min()) / DAY + g.h.iloc[-1] / 24
    n = len(D)
    r, r8 = D.r, D.r8
    base = np.isclose(D.r, 0.0001 * D.h / 8, atol=2e-7)
    print(f"\n== {name}: перпов {D.s.nunique()}, начислений {n:,}, монето-суток {days:,.0f}")
    print("  ставка на 8 ч, квантили 1/5/25/50/75/95/99%: " + " ".join(f"{v:+.3%}" for v in r8.quantile([.01, .05, .25, .5, .75, .95, .99]))
          + f"; среднее {r8.mean():+.4%}; на базовой ставке (0,01% за 8 ч) {base.mean():.0%}")
    print(f"  кто платит: лонги (r > базы) {(r8 > 0.0001 + 1e-7).mean():.0%} начислений, шорты (r < 0) {(r < 0).mean():.0%}; "
          f"средний фандинг в сутки {(D.r.sum() / days):+.3%} (+ лонги платят шортам)")
    print("  за начисление ≤ −0,5% / ≤ −1% / ≤ −2% / ≥ +0,5% / ≥ +1% (в скобках — на 100 монето-месяцев): " + " / ".join(
        f"{c.sum()} ({c.sum() / days * 3044:.1f})" for c in (r <= -0.005, r <= -0.01, r <= -0.02, r >= 0.005, r >= 0.01)))
    print(f"  в пересчёте на 8 ч ≤ −0,5%: {(r8 <= -0.005).mean():.2%} начислений, ≥ +0,5%: {(r8 >= 0.005).mean():.2%}; "
          f"≤ −0,1%: {(r8 <= -0.001).mean():.1%}, ≥ +0,1%: {(r8 >= 0.001).mean():.1%}")
    hh = D.groupby("h").size() / n
    tt = D.groupby("h").h.sum() / D.h.sum()
    print("  интервал (доля начислений / доля времени): " + ", ".join(f"{int(k)} ч {hh[k]:.0%}/{tt[k]:.0%}" for k in sorted(hh.index)))
    sw, sw_down, ep_neg, ep_pos, ep_n5 = 0, [], [], [], []
    for s, g in D.groupby("s"):
        g = g.reset_index(drop=True)
        ch = np.flatnonzero(np.diff(g.h.values) != 0) + 1
        sw += len(ch)
        for i in ch:
            if g.h.values[i] < g.h.values[i - 1]:
                sw_down.append((s, int(g.t.values[i]), g.h.values[i - 1], g.h.values[i], float(g.r8.values[i - 1])))
        ep_neg += episodes(g, g.r8 <= -0.001); ep_pos += episodes(g, g.r8 >= 0.001); ep_n5 += episodes(g, g.r <= -0.005)
    W = pd.DataFrame(sw_down, columns=["s", "t", "h0", "h1", "r8prev"])
    print(f"  смены интервала: {sw} ({sw / days * 3044:.1f} на 100 монето-месяцев), из них укорочений {len(W)} "
          f"({len(W) / days * 3044:.1f}); укорочение до 1 ч: {(W.h1 == 1).sum()}; ставка перед укорочением на 8 ч: медиана "
          f"{W.r8prev.median():+.3%}, отрицательная у {(W.r8prev < 0).mean():.0%}")
    for nm, E in (("≤ −0,1% за 8 ч", ep_neg), ("≥ +0,1% за 8 ч", ep_pos), ("≤ −0,5% за начисление", ep_n5)):
        X = pd.DataFrame(E, columns=["t", "hours", "n"])
        if len(X):
            print(f"  эпизоды {nm}: {len(X)} ({len(X) / days * 3044:.1f} на 100 монето-месяцев); длительность ч: медиана "
                  f"{X.hours.median():.0f}, 75% {X.hours.quantile(.75):.0f}, 90% {X.hours.quantile(.9):.0f}, ≥ 24 ч "
                  f"{(X.hours >= 24).mean():.0%}; начислений медиана {X.n.median():.0f}")


def caps(D):
    """Снимок потолков ставки (www.binance.com/fapi/v1/fundingInfo) и мода крайних начислений по монетам."""
    path = f"{OUT}/fundingInfo.json"
    if not os.path.exists(path):
        import urllib.request
        req = urllib.request.Request("https://www.binance.com/fapi/v1/fundingInfo", headers={"User-Agent": "research-script/1.0"})
        open(path, "wb").write(urllib.request.urlopen(req, timeout=30).read())
    FI = {x["symbol"][:-4]: x for x in json.load(open(path)) if x["symbol"].endswith("USDT")}
    U = json.load(open(f"{OUT}/universe.json"))
    rows = []
    for s, u in U.items():
        if s in FI and u["live1"] >= T1 - 2 * DAY:
            x = FI[s]
            rows.append((s, u["spot0"] is None, float(x["adjustedFundingRateCap"]), float(x["adjustedFundingRateFloor"]),
                         int(x["fundingIntervalHours"])))
    C = pd.DataFrame(rows, columns=["s", "ns", "cap", "floor", "h"])
    print(f"\n== fundingInfo (снимок 23.11.2026): символов с особыми настройками {len(FI)}; из живых перпов вселенной {len(C)}")
    for ns, g in C.groupby("ns"):
        print(f"  {'без спота' if ns else 'со спотом'}: {len(g)}; потолок (мода/медиана) {g.cap.mode().iloc[0]:.2%}/{g.cap.median():.2%}, "
              f"пол {g.floor.mode().iloc[0]:.2%}/{g.floor.median():.2%}; интервал: " +
              ", ".join(f"{k} ч — {v}" for k, v in g.h.value_counts().sort_index().items()))
    # упор в пол/потолок по истории: начисление на уровне снимка (до 0,5 б.п.)
    m = D.merge(C[["s", "cap", "floor"]], on="s", how="inner")
    m = m[m.t >= SNAP0]
    for ns, g in m.groupby("ns"):
        at_f = np.isclose(g.r, g.floor, atol=5e-5); at_c = np.isclose(g.r, g.cap, atol=5e-5)
        print(f"  07–10.2026, {'без спота' if ns else 'со спотом'}: начислений на полу (по снимку) {at_f.mean():.2%}, на потолке "
              f"{at_c.mean():.2%}; монет, хоть раз на полу, {g[at_f].s.nunique()} из {g.s.nunique()}")


def main():
    D = load()
    D["to7"] = turnover(D)
    edges = [2.3e6, 5.3e6, 12.4e6, 41.5e6]                      # пятые доли оборота — как в premium.py
    D["bk"] = np.searchsorted(edges, D.to7.fillna(0).values)
    describe(D[D.ns], "без спота")
    describe(D[~D.ns], "со спотом")
    for h, (lo, hi) in (("1-я половина", (T0, MID)), ("2-я половина", (MID, T1))):
        describe(D[D.ns & (D.t >= lo) & (D.t < hi)], f"без спота, {h}")
        describe(D[~D.ns & (D.t >= lo) & (D.t < hi)], f"со спотом, {h}")
    for b in range(5):
        describe(D[D.ns & (D.bk == b)], f"без спота, оборот {b + 1}")
        describe(D[~D.ns & (D.bk == b)], f"со спотом, оборот {b + 1}")
    late = D[D.ns & D.snap & (D.t >= SNAP0)]
    describe(late[late["self"] > 0], "07–10.2026, сам перп в индексе")
    describe(late[late["self"] == 0], "07–10.2026, перпа в индексе нет")
    describe(late[late.alpha > 0], "07–10.2026, Alpha в индексе")
    describe(late[late.alpha == 0], "07–10.2026, Alpha в индексе нет")
    U = json.load(open(f"{OUT}/universe.json"))
    trs = {s for s, u in U.items() if u["spot0"] and max(u["live0"], T0) + 30 * DAY < u["spot0"] < min(u["live1"], T1) - 30 * DAY}
    tr = D[D.s.isin(trs)]
    print(f"\nперпов с переходом «без спота → спот» и 30 сут по обе стороны: {len(trs)}")
    describe(tr[(tr.t >= tr.spot0 - 30 * DAY) & (tr.t < tr.spot0 - 3 * DAY)], "за 30…3 сут до спота")
    describe(tr[(tr.t >= tr.spot0 + 3 * DAY) & (tr.t < tr.spot0 + 30 * DAY)], "через 3…30 сут после спота")
    caps(D)
    D.to_pickle(f"{TMP}/funding_panel.pkl")


if __name__ == "__main__":
    main()
