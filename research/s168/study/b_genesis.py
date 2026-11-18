"""s167 area B, step 5: derived 'insider' label on a sample — first-ever inflow of the token to the effective sender
(eth_getLogs over the whole history with the recipient topic, Tenderly public gateway, ~1 request/1.5 s), then the type of
that first source: mint (zero address) / exchange / labelled DEX-bridge-contract / other contract (vesting, distributor,
multisig...) / EOA. Sample: random events 10.2024–11.2026 whose effective sender is an unlabelled EOA or Safe."""
import json, random, re, time, urllib.request, collections
SP = "/home/user/mc_data/s168"
RPC = "https://gateway.tenderly.co/public/mainnet"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ev = [e for e in json.load(open(f"{SP}/work/b_events.json")) if e["date"] >= "2024-10-01"]
hop = json.load(open("/home/user/mc_data/s160/cache_hop.json"))
CEX = json.load(open("/home/user/mc_data/s160/sets.json"))["cex"]
BS = json.load(open(f"{SP}/work/bs_meta.json"))
ST = json.load(open(f"{SP}/work/struct.json"))
DEP = re.compile(r"deposit|\bdep\b", re.I)
def eff(e):
    a = e["frm"]
    if any(DEP.search(t) for t in BS.get(a, [])):
        h = hop.get(f"{e['tok']}:{a}:{e['block']}")
        a = h[0] if h and h[0] else None
    return a if a and a not in CEX else None
cand = [(e, eff(e)) for e in ev]
cand = [(e, a) for e, a in cand if a and (ST.get(a, {}).get("safe") or not ST.get(a, {}).get("code"))]
random.seed(167); smp = random.sample(cand, 110)
def rpc(body):
    for k in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(RPC, data=json.dumps(body).encode(), headers=UA), timeout=90))
        except Exception:
            time.sleep(4 + 4 * k)
    return {}
pad = lambda x: "0x" + "0" * 24 + x[2:]
rows = []
for e, a in smp:
    r = rpc({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [{"fromBlock": "0x0", "toBlock": hex(e["block"]), "address": e["tok"], "topics": [T0, None, pad(a)]}]})
    logs = r.get("result")
    time.sleep(1.5)
    if not isinstance(logs, list):
        rows.append(dict(sym=e["sym"], cls="rpc_fail", err=str(r.get("error"))[:80])); continue
    if not logs:
        rows.append(dict(sym=e["sym"], cls="no_inflow_found")); continue
    first = min(logs, key=lambda x: (int(x["blockNumber"], 16), int(x["logIndex"], 16)))
    src = "0x" + first["topics"][1][-40:]
    nin = len(logs); fb = int(first["blockNumber"], 16)
    if src == "0x" + "0" * 40:
        c = "mint_to_sender"
    elif src in CEX or any(DEP.search(t) for t in BS.get(src, [])):
        c = "from_exchange"
    else:
        g = rpc({"jsonrpc": "2.0", "id": 1, "method": "eth_getCode", "params": [src, "latest"]}); time.sleep(1.0)
        c = "from_contract" if len((g or {}).get("result") or "0x") > 2 else "from_eoa"
    rows.append(dict(sym=e["sym"], date=e["date"], frac=round(e["frac"] * 100, 2), sender=a, first_src=src, first_block=fb,
                     event_block=e["block"], age_days=round((e["block"] - fb) * 12 / 86400), n_inflows=nin, cls=c))
json.dump(rows, open(f"{SP}/work/genesis_sample.json", "w"))
c = collections.Counter(r["cls"] for r in rows)
print("sample", len(rows), dict(c))
ok = [r for r in rows if "age_days" in r]
if ok:
    import statistics as st
    print("median holding age (days) since first inflow:", st.median(r["age_days"] for r in ok))
    for k in ("mint_to_sender", "from_contract", "from_eoa", "from_exchange"):
        g = [r["age_days"] for r in ok if r["cls"] == k]
        if g: print(f"  {k}: n={len(g)} median age {st.median(g)} d, share with age>180d {sum(x>180 for x in g)/len(g):.0%}")
