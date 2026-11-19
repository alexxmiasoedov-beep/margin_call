"""s201: сопоставление перпов Binance (s2/k2y.pkl, живые в окне 2025-11-19 … 2026-10-18) и slug Santiment.

Кандидаты — проекты Santiment с тем же тикером (без приставок 1000, 1000000, 1M). Проверка цены: дневная price_usd
(метрика без ограничений) за окно, медиана отношения «закрытие перпа / (множитель × цена Santiment)» по общим дням
должна быть в 0,8…1,25 (как в 🐋 и 🔑). При нескольких прошедших — ближайший к 1, затем с большим числом общих дней.
Итог — /home/user/mc_data/s201/map.csv (s, base, mult, slug, ticker, infrastructure, ratio, days)."""
import json
import pickle
import re

import numpy as np
import pandas as pd

import san

D = san.D
U = pickle.load(open(f"{D}/perp_daily.pkl", "rb"))
L, P = U["live"], U["daily"]
a = pd.Timestamp("2025-11-19", tz="UTC").timestamp()
b = pd.Timestamp("2026-10-18", tz="UTC").timestamp()
alive = sorted(L[(L.live1 >= a) & (L.live0 <= b)].s)
PR = json.load(open(f"{D}/projects.json"))
by_tick = {}
for p in PR:
    by_tick.setdefault((p["ticker"] or "").upper(), []).append(p)


def base(s):
    for pre, m in (("1000000", 1e6), ("100000", 1e5), ("10000", 1e4), ("1000", 1e3), ("1M", 1e6)):
        if s.startswith(pre) and len(s) > len(pre) and not s[len(pre):].isdigit():
            return s[len(pre):], m
    return s, 1.0


cand = {}
for s in alive:
    bs, m = base(s)
    for p in by_tick.get(bs.upper(), []):
        cand.setdefault(s, []).append((p["slug"], p["ticker"], p["infrastructure"], m, bs))
slugs = sorted({c[0] for v in cand.values() for c in v})
print("перпов живых в окне:", len(alive), "с кандидатами:", len(cand), "slug-кандидатов:", len(slugs))

# цена Santiment по дням, по ~220 slug за вызов
prices = []
CH = 220
for i in range(0, len(slugs), CH):
    part = slugs[i:i + CH]
    js, q = san.per_slug("price_usd", part, "2025-11-20T00:00:00Z", "2026-10-18T00:00:00Z", "1d", tag="map_price")
    if js.get("errors"):
        print("ошибка:", js["errors"][0])
    prices.append(san.per_slug_frame(js))
PX = pd.concat(prices, ignore_index=True).dropna(subset=["value"])
PX["d"] = PX.datetime.dt.floor("D")
PX.to_pickle(f"{D}/price_usd_daily.pkl")
print("цен Santiment:", len(PX), "slug с ценой:", PX.slug.nunique())

C = P.set_index(["s", "d"]).c
rows = []
for s, cs in cand.items():
    best = None
    for slug, tick, infra, m, bs in cs:
        x = PX[PX.slug == slug].set_index("d").value
        x = x[x > 0]
        try:
            pc = C.loc[s]
        except KeyError:
            continue
        j = pc.index.intersection(x.index)
        if len(j) < 20:
            r, nd = np.nan, len(j)
        else:
            r, nd = float(np.median(pc.loc[j].values / (m * x.loc[j].values))), len(j)
        ok = 0.8 <= r <= 1.25 if r == r else False
        rec = dict(s=s, base=bs, mult=m, slug=slug, ticker=tick, infrastructure=infra, ratio=r, days=nd, ok=ok,
                   n_cand=len(cs))
        rows.append(rec)
M = pd.DataFrame(rows)
M.to_csv(f"{D}/map_candidates.csv", index=False)
# Ключ: у Santiment для токенов в нескольких сетях — отдельные slug на каждую сеть (bnb-, arb-, o-, p-, a-, sol-):
# bnb-floki-inu и floki-inu-v2, arb-gmx и a-gmx, p-aave и o-aave. Ончейн-метрики считаются по сети slug.
# Основной slug — без приставки сети, среди них ближе к 1 по цене; варианты сетей — в map_variants.csv.
PREF = re.compile(r"^(bnb|arb|o|p|a|sol|base|op)-")
good = M[M.ok].copy()
good["dist"] = (np.log(good.ratio)).abs()
good["chain_prefixed"] = good.slug.str.match(PREF)
good = good.sort_values(["s", "chain_prefixed", "dist", "days"], ascending=[True, True, True, False])
good[good.duplicated("s", keep="first")].drop(columns=["dist", "ok"]).to_csv(f"{D}/map_variants.csv", index=False)
good = good.drop_duplicates("s")
good.drop(columns=["dist", "ok"]).to_csv(f"{D}/map.csv", index=False)
print("сопоставлено перпов:", len(good), "из", len(cand), "с кандидатами")
amb = M.groupby("s").ok.sum()
print("перпов, где цену прошли ≥ 2 slug:", int((amb >= 2).sum()))
for s in amb[amb >= 2].index:
    g = M[(M.s == s) & M.ok]
    print(f"  {s}: " + "; ".join(f"{r.slug}({r.infrastructure},{r.ratio:.3f})" for r in g.itertuples())
          + f" → {good[good.s == s].slug.iloc[0]}")
print("инфраструктура основных slug:", good.infrastructure.fillna("None").value_counts().to_dict())
bad = sorted(set(cand) - set(good.s))
print("не прошли цену:", len(bad), " ".join(bad))
