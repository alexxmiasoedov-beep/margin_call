# Снимок очереди анбондинга (Cosmos SDK): все незавершённые unbonding_delegations по валидаторам.
# Оценка: сколько крупных (≥ порога доли обращения) завершений придётся на ближайшие 21 сутки.
import json, sys, time, urllib.request, datetime, collections
UA = {"User-Agent": "research-script/1.0"}
chain, denom_exp, circ = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
base = f"https://rest.cosmos.directory/{chain}"
def get(path):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(base + path, headers=UA), timeout=40) as r:
                return json.load(r)
        except Exception as e:
            err = e; time.sleep(2)
    print("FAIL", path, err, file=sys.stderr); return None
vals = []; key = ""
while True:
    d = get("/cosmos/staking/v1beta1/validators?pagination.limit=500" + (f"&pagination.key={urllib.parse.quote(key)}" if key else ""))
    if not d: break
    vals += [v["operator_address"] for v in d["validators"]]
    key = (d.get("pagination") or {}).get("next_key") or ""
    if not key: break
import urllib.parse
print(chain, "валидаторов", len(vals))
entries = []
for i, v in enumerate(vals):
    k = ""
    while True:
        d = get(f"/cosmos/staking/v1beta1/validators/{v}/unbonding_delegations?pagination.limit=1000" + (f"&pagination.key={urllib.parse.quote(k)}" if k else ""))
        if not d: break
        for u in d.get("unbonding_responses", []):
            for e in u["entries"]:
                entries.append((u["delegator_address"], e["completion_time"][:19], float(e["balance"]) / 10 ** denom_exp))
        k = (d.get("pagination") or {}).get("next_key") or ""
        if not k: break
    time.sleep(0.05)
# склеить по делегатору и дню завершения
agg = collections.defaultdict(float)
for a, t, b in entries:
    agg[(a, t[:10])] += b
tot = sum(agg.values())
sizes = sorted(agg.values(), reverse=True)
print(f"записей {len(entries)}, пар делегатор-день {len(agg)}, всего в очереди {tot:,.0f} ({100*tot/circ:.2f}% обращения)")
for thr in (0.0005, 0.001, 0.0025, 0.005):
    n = sum(1 for s in sizes if s >= thr * circ)
    print(f"  завершений ≥ {100*thr:.2f}% обращения за 21 сут: {n}  (≈ {n*30/21:.1f} в месяц)")
byday = collections.Counter()
for (a, day), b in agg.items(): byday[day] += b
big_days = sorted(byday.items(), key=lambda x: -x[1])[:5]
print("  крупнейшие сутки завершений:", [(d, f'{100*b/circ:.3f}%') for d, b in big_days])
