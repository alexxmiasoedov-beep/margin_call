"""s201: справочники Santiment — сети (getAvailableBlockchains) и все проекты (allProjects: slug, тикер, сеть)."""
import json
import san

q1 = '''{
  getAvailableBlockchains {
    blockchain
    slug
    infrastructure
    createdOn
    hasLabelMetrics
    hasMinersMetrics
    hasExchangeMetrics
    hasTopHoldersMetrics
    hasPureOnchainMetrics
    hasOnchainFinancialMetrics
  }
}'''
js = san.gql(q1, "blockchains", {"metric": "getAvailableBlockchains"})
B = js["data"]["getAvailableBlockchains"]
json.dump(B, open(f"{san.D}/blockchains.json", "w"))
print("сеть | slug | инфраструктура | биржевые | метки | держатели | чистый ончейн | финансовые")
for b in B:
    print(f"{b['blockchain']} | {b['slug']} | {b['infrastructure']} | {b['hasExchangeMetrics']} | {b['hasLabelMetrics']} | "
          f"{b['hasTopHoldersMetrics']} | {b['hasPureOnchainMetrics']} | {b['hasOnchainFinancialMetrics']}")

q2 = '''{
  allProjects {
    slug
    name
    ticker
    infrastructure
  }
}'''
js = san.gql(q2, "all_projects", {"metric": "allProjects"})
P = js["data"]["allProjects"]
json.dump(P, open(f"{san.D}/projects.json", "w"))
import collections
print("\nпроектов:", len(P))
print("инфраструктура:", collections.Counter(p["infrastructure"] for p in P).most_common(25))
