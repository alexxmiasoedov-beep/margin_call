"""CoinGecko (без ключа): список монет с капитализацией и FDV, затем дневная история капитализации и объёма за год (публичный API отдаёт не больше 365 дней)
для монет с фьючерсом Binance → s7/cg/. Медленно (лимит публичного API), с паузами и повторами при 429."""
import json, subprocess, time, pickle, re, os
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
K = pickle.load(open("s2/k2y.pkl", "rb")); bases = {strip(s).lower() for s in K}
def get(url, tries=8):
    for k in range(tries):
        r = subprocess.run(["curl", "-sS", "-m", "60", "-w", "\n%{http_code}", url], capture_output=True, text=True)
        body, _, code = r.stdout.rpartition("\n")
        if code == "200":
            try: return json.loads(body)
            except Exception: pass
        time.sleep(15 + 15 * k if code == "429" else 5)
    return None
if not os.path.exists("s7/cg/markets.json"):
    M = []
    for p in range(1, 15):
        j = get(f"https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={p}")
        if not j: break
        M += j; print("страница", p, len(M), flush=True); time.sleep(6)
    json.dump(M, open("s7/cg/markets.json", "w"))
M = json.load(open("s7/cg/markets.json"))
best = {}
for x in M:
    sy = (x.get("symbol") or "").lower()
    if sy in bases and (sy not in best or (x.get("market_cap") or 0) > (best[sy].get("market_cap") or 0)): best[sy] = x
print("сопоставлено монет:", len(best), "из", len(bases), flush=True)
json.dump({k: v["id"] for k, v in best.items()}, open("s7/cg/map.json", "w"))
for i, (sy, x) in enumerate(sorted(best.items())):
    fn = f"s7/cg/{sy}.json"
    if os.path.exists(fn): continue
    j = get(f"https://api.coingecko.com/api/v3/coins/{x['id']}/market_chart?vs_currency=usd&days=365&interval=daily")
    json.dump(j or {}, open(fn, "w")); time.sleep(6)
    if i % 25 == 0: print(i, sy, len((j or {}).get("market_caps", [])), flush=True)
print("готово", flush=True)
