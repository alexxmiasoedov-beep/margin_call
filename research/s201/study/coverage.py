"""s201: покрытие вселенной метриками Santiment — metadata { availableSlugs availableSelectors … } по одной метрике
за вызов (allProjects { availableMetrics } для многих проектов Santiment запрещает — 1 вызов потрачен на отказ).
Итог — /home/user/mc_data/s201/meta.json и сводка по сетям основного slug перпов."""
import collections
import json
import sys

import pandas as pd

import san

D = san.D
G = pd.read_csv(f"{D}/map.csv")
V = pd.read_csv(f"{D}/map_variants.csv")
PR = {p["slug"]: p for p in json.load(open(f"{D}/projects.json"))}
MET = ["exchange_inflow", "labelled_historical_balance", "social_volume_total", "social_dominance_total",
       "sentiment_weighted_total", "age_consumed", "dormant_circulation_365d", "mvrv_usd",
       "whale_transaction_count_100k_usd_to_inf", "active_deposits", "network_growth", "daily_active_addresses",
       "amount_in_top_holders", "historical_balance_centralized_exchanges"]
if len(sys.argv) > 1:
    MET = sys.argv[1].split(",")
try:
    META = json.load(open(f"{D}/meta.json"))
except FileNotFoundError:
    META = {}
for m in MET:
    q = (f'{{\n  getMetric(metric: "{m}") {{\n    metadata {{\n      availableSlugs\n      availableSelectors\n'
         f'      availableAggregations\n      defaultAggregation\n      minInterval\n      dataType\n      isTimebound\n'
         f'    }}\n  }}\n}}')
    js = san.gql(q, "meta", {"metric": m})
    if js.get("errors"):
        print(m, "ошибка:", js["errors"][0].get("message"))
        continue
    META[m] = js["data"]["getMetric"]["metadata"]
json.dump(META, open(f"{D}/meta.json", "w"))

infra_all = collections.Counter((p["infrastructure"] or "None") for p in PR.values())
g_inf = dict(zip(G.slug, G.infrastructure.fillna("None")))
print("метрика | селекторы | шаг | агрегация | slug всего | из них по сетям (все проекты) | перпов с метрикой | перпы по сетям")
for m in MET:
    md = META.get(m)
    if not md:
        continue
    av = set(md["availableSlugs"] or [])
    by_all = collections.Counter((PR.get(s, {}).get("infrastructure") or "None") for s in av)
    have = [s for s in G.slug if s in av]
    by_p = collections.Counter(g_inf[s] for s in have)
    print(f"{m} | {md['availableSelectors']} | {md['minInterval']} | {md['defaultAggregation']} | {len(av)} | "
          f"{dict(by_all.most_common(10))} | {len(have)} | {dict(by_p.most_common(10))}")
print("\nварианты сетей перпов (bnb-, arb-, o-, p-, a-, sol-) — какие метрики есть:")
for r in V.itertuples():
    keys = [m for m in MET if r.slug in set((META.get(m) or {}).get("availableSlugs") or [])]
    print(f"  {r.s} {r.slug} ({r.infrastructure}): {keys}")
