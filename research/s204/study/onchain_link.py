#!/usr/bin/env python3
"""s204: видны ли «всплески депозитов» Upbit/Bithumb в Ethereum (только описательно, доходы не считаются).

Ончейн: /home/user/mc_data/s195_deposits.pkl — переводы ERC-20 >= 0,05% обращения на помеченные адреса бирж
(сбор s160, 261 токен с перпом, по 05.11.2026); exch in {Upbit, Bithumb}.
Флаги: upbit_days_D.csv (сутки флага d, окно подсчёта [d-1 00:00, d 00:00) UTC),
       bithumb_hist.csv тип 03 (окно — 24 ч до начала флага, время KST -> UTC).
Вопросы: 1) какая доля флагов D по токенам из сбора имела крупный перевод на ту же биржу в окне;
         2) какая доля крупных переводов (>= 0,5% обращения) получила флаг D той же биржи в следующем пересчёте.
"""
import csv, json, collections
from datetime import datetime, timedelta, timezone
import pandas as pd

OUT = "/home/user/mc_data/s204"


def bithumb_symbols():
    d = json.load(open(OUT + "/web/bithumb_site/intro.json"))["data"]
    return {c["coinType"]: c["coinSymbol"] for c in d["coinList"]}


def main():
    dep = pd.read_pickle("/home/user/mc_data/s195_deposits.pkl")
    dep = dep[dep["exch"].isin(["Upbit", "Bithumb"])].copy()
    dep["dt"] = pd.to_datetime(dep["t"], unit="s")
    tmax = dep["dt"].max()
    # тикер сбора -> база (без множителя 1000 и т.п.)
    def base(s):
        for pre in ("1000000", "10000", "1000", "1M"):
            if s.startswith(pre) and len(s) > len(pre):
                return s[len(pre):]
        return s
    dep["coin"] = dep["perp"].map(base)
    universe = set(dep["coin"])
    all_univ = set(pd.read_pickle("/home/user/mc_data/s195_deposits.pkl", )["perp"].map(base))
    print("ончейн: переводов на Upbit/Bithumb", len(dep), "до", tmax, "токенов в сборе", len(all_univ))
    by = {(ex, c): g.sort_values("dt") for (ex, c), g in dep.groupby(["exch", "coin"])}

    def any_dep(ex, coin, t0, t1, thr):
        g = by.get((ex, coin))
        if g is None:
            return False
        m = (g["dt"] >= t0) & (g["dt"] < t1) & (g["frac"] >= thr)
        return bool(m.any())

    # --- Upbit D
    U = [x for x in csv.DictReader(open(OUT + "/upbit_days_D.csv")) if x["new_episode"] == "1"]
    res = collections.Counter()
    for x in U:
        d = datetime.fromisoformat(x["day"])
        t1 = d  # 00:00 UTC дня флага
        t0 = d - timedelta(days=1)
        if t1 > tmax or x["coin"] not in all_univ:
            continue
        res["n"] += 1
        res["dep005"] += any_dep("Upbit", x["coin"], t0, t1, 0.0005)
        res["dep05"] += any_dep("Upbit", x["coin"], t0, t1, 0.005)
        res["dep005_3d"] += any_dep("Upbit", x["coin"], t0 - timedelta(days=2), t1, 0.0005)
    n = res["n"]
    print(f"\nUpbit D (новые эпизоды, токены сбора, до {tmax:%Y-%m-%d}): {n}; с переводом на Upbit в окне 24 ч "
          f">= 0,05% обращения {res['dep005']} ({res['dep005'] / max(1, n):.0%}), >= 0,5% {res['dep05']} "
          f"({res['dep05'] / max(1, n):.0%}); >= 0,05% за 72 ч {res['dep005_3d']} ({res['dep005_3d'] / max(1, n):.0%})")
    # обратное: крупные переводы на Upbit -> D в ближайший пересчёт 01:00 UTC (окно [d-1, d))
    Uset = {(x["coin"], x["day"]) for x in csv.DictReader(open(OUT + "/upbit_days_D.csv"))}
    for thr in (0.005, 0.01, 0.02):
        g = dep[(dep["exch"] == "Upbit") & (dep["frac"] >= thr) & (dep["dt"] >= datetime(2026, 3, 23))]
        # один перевод на монету в сутки (самый крупный)
        g = g.assign(day=(g["dt"].dt.floor("D") + pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d"))
        g = g.sort_values("frac").groupby(["coin", "day"]).tail(1)
        hit = sum((c, dd) in Uset for c, dd in zip(g["coin"], g["day"]))
        print(f"  переводы на Upbit >= {thr:.1%} обращения (монето-сутки) с 23.03.2026: {len(g)}, "
              f"из них с флагом D на следующий пересчёт {hit} ({hit / max(1, len(g)):.0%})")
    # --- Bithumb D (тип 03)
    sym = bithumb_symbols()
    B = [r for r in csv.DictReader(open(OUT + "/bithumb_hist.csv")) if r["warningType"] == "03"]
    starts = collections.defaultdict(list)
    for r in B:
        c = sym.get(r["coinType"])
        if not c:
            continue
        t = datetime.strptime(r["startDateTime"], "%Y-%m-%d %H:%M:%S") - timedelta(hours=9)
        starts[c].append(t)
    res = collections.Counter()
    per_year = collections.defaultdict(collections.Counter)
    for c, ts in starts.items():
        ts.sort()
        prev = None
        for t in ts:
            new = prev is None or (t - prev) > timedelta(hours=25)
            prev = t
            if not new or t > tmax or c not in all_univ:
                continue
            res["n"] += 1
            a = any_dep("Bithumb", c, t - timedelta(hours=24), t, 0.0005)
            b = any_dep("Bithumb", c, t - timedelta(hours=24), t, 0.005)
            c3 = any_dep("Bithumb", c, t - timedelta(hours=72), t, 0.0005)
            res["dep005"] += a; res["dep05"] += b; res["dep005_3d"] += c3
            y = t.year
            per_year[y]["n"] += 1; per_year[y]["dep005"] += a
    n = res["n"]
    print(f"\nBithumb D (новые, токены сбора, до {tmax:%Y-%m-%d}): {n}; с переводом на Bithumb в 24 ч до флага "
          f">= 0,05% {res['dep005']} ({res['dep005'] / max(1, n):.0%}), >= 0,5% {res['dep05']} ({res['dep05'] / max(1, n):.0%}); "
          f">= 0,05% за 72 ч {res['dep005_3d']} ({res['dep005_3d'] / max(1, n):.0%})")
    print("  по годам (n, доля с переводом >= 0,05% за 24 ч):",
          {y: (v["n"], round(v["dep005"] / max(1, v["n"]), 2)) for y, v in sorted(per_year.items())})
    Bset = collections.defaultdict(list)
    for c, ts in starts.items():
        Bset[c] = ts
    for thr in (0.005, 0.01, 0.02):
        g = dep[(dep["exch"] == "Bithumb") & (dep["frac"] >= thr) & (dep["dt"] >= datetime(2023, 7, 5))]
        g = g.assign(day=g["dt"].dt.strftime("%Y-%m-%d")).sort_values("frac").groupby(["coin", "day"]).tail(1)
        hit = 0
        for c, t in zip(g["coin"], g["dt"]):
            hit += any(timedelta(0) < (u - t.to_pydatetime()) <= timedelta(hours=30) for u in Bset.get(c, []))
        print(f"  переводы на Bithumb >= {thr:.1%} обращения (монето-сутки) с 05.07.2023: {len(g)}, "
              f"с флагом D Bithumb в следующие 30 ч {hit} ({hit / max(1, len(g)):.0%})")


if __name__ == "__main__":
    main()
