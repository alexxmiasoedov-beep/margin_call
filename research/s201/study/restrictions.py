"""s201: разбор getAccessRestrictions (тариф без ключа): какие метрики доступны, с каким шагом и окном."""
import json, glob, collections
import san
q = '''{
  getAccessRestrictions(filter: METRIC) {
    name
    minInterval
    isAccessible
    isRestricted
    isDeprecated
    restrictedFrom
    restrictedTo
    availableVersions { version versionName }
  }
}'''
js = san.gql(q, "access_restrictions", {"metric": "*"})
R = js["data"]["getAccessRestrictions"]
json.dump(R, open(f"{san.D}/restrictions.json", "w"))
acc = [r for r in R if r["isAccessible"]]
free = [r for r in acc if not r["isRestricted"]]
restr = [r for r in acc if r["isRestricted"]]
print(f"всего метрик {len(R)}, доступны {len(acc)} (без ограничений {len(free)}, с окном {len(restr)}), недоступны {len(R)-len(acc)}")
print("окна доступных с ограничением:", collections.Counter((r["restrictedFrom"], r["restrictedTo"]) for r in restr).most_common(5))
print("шаг доступных:", collections.Counter(r["minInterval"] for r in acc).most_common())
print("версии:", collections.Counter(tuple(v["versionName"] or v["version"] for v in r["availableVersions"]) for r in acc).most_common(6))
want = ["social_volume_total", "social_dominance_total", "unique_social_volume_total_1d", "unique_social_volume_total_1h",
        "sentiment_positive_total", "sentiment_negative_total", "sentiment_balance_total", "sentiment_weighted_total",
        "age_consumed", "age_destroyed", "dormant_circulation_90d", "dormant_circulation_180d", "dormant_circulation_365d",
        "exchange_inflow", "exchange_outflow", "exchange_balance", "exchange_inflow_usd", "exchange_inflow_per_exchange",
        "exchange_outflow_per_exchange", "exchange_balance_per_exchange", "active_deposits", "active_deposits_5m",
        "active_deposits_per_exchange", "deposit_transactions", "deposit_transactions_per_exchange",
        "whale_transaction_count_100k_usd_to_inf", "whale_transaction_count_1m_usd_to_inf", "mvrv_usd", "mvrv_usd_30d",
        "mvrv_usd_365d", "mvrv_usd_intraday", "network_growth", "daily_active_addresses", "active_addresses_24h",
        "supply_on_exchanges", "percent_of_total_supply_on_exchanges", "price_usd", "volume_usd", "marketcap_usd",
        "circulation", "transaction_volume", "dev_activity", "social_volume_telegram", "social_volume_twitter",
        "social_volume_reddit", "community_messages_count_total", "amount_in_top_holders", "whale_transaction_volume_100k_usd_to_inf"]
by = {r["name"]: r for r in R}
print("\nметрика | доступна | ограничена | шаг | с | по | версии")
for w in want:
    r = by.get(w)
    if not r:
        print(f"{w} | нет в списке"); continue
    print(f"{w} | {r['isAccessible']} | {r['isRestricted']} | {r['minInterval']} | {r['restrictedFrom']} | {r['restrictedTo']} | "
          + ",".join(v['versionName'] or v['version'] for v in r['availableVersions']))
# группы по корню имени среди доступных
roots = collections.Counter()
for r in acc:
    n = r["name"]
    for p in ("social_volume", "social_dominance", "sentiment", "exchange", "dormant_circulation", "age_", "mvrv", "whale",
              "active_deposits", "deposit_", "withdrawal", "network_growth", "active_addresses", "supply", "labelled", "holders",
              "top_holders", "amount_in", "price", "volume", "funding", "open_interest", "dex", "nft", "dev_activity",
              "github", "spent_coins", "circulation", "velocity", "transaction", "nvt", "realized", "rsi", "unique_social",
              "community", "twitter", "trending", "liquidations", "etf", "miners", "fees", "total_supply", "marketcap"):
        if n.startswith(p):
            roots[p] += 1; break
    else:
        roots["прочее"] += 1
print("\nдоступные по группам:", roots.most_common())
