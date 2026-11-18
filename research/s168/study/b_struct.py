"""s167 area B, step 4: structural labels for effective senders of large deposits (10.2024–11.2026): contract or EOA
(eth_getCode, latest) and Safe multisig (eth_call getThreshold()). Public RPC without key, JSON-RPC batches of 40.
Effective sender = 7-day upstream source when the direct sender is an exchange deposit address, else the sender."""
import json, re, time, urllib.request, collections
SP = "/home/user/mc_data/s168"
RPC = "https://ethereum-rpc.publicnode.com"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
ev = [e for e in json.load(open(f"{SP}/work/b_events.json")) if e["date"] >= "2024-10-01"]
hop = json.load(open("/home/user/mc_data/s160/cache_hop.json"))
CEX = json.load(open("/home/user/mc_data/s160/sets.json"))["cex"]
BS = json.load(open(f"{SP}/work/bs_meta.json"))
DEP = re.compile(r"deposit|\bdep\b", re.I)
eff = []
for e in ev:
    a = e["frm"]
    if any(DEP.search(t) for t in BS.get(a, [])):
        h = hop.get(f"{e['tok']}:{a}:{e['block']}")
        a = h[0] if h and h[0] else None
    if a and a not in CEX:
        eff.append(a)
U = sorted(set(eff))
print("events", len(ev), "with effective non-CEX sender", len(eff), "unique", len(U), flush=True)
def batch(reqs):
    for k in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(RPC, data=json.dumps(reqs).encode(), headers=UA), timeout=60))
        except Exception:
            time.sleep(3 + 3 * k)
    return []
res = {}
for i in range(0, len(U), 40):
    part = U[i:i + 40]
    reqs = []
    for j, a in enumerate(part):
        reqs.append({"jsonrpc": "2.0", "id": 2 * j, "method": "eth_getCode", "params": [a, "latest"]})
        reqs.append({"jsonrpc": "2.0", "id": 2 * j + 1, "method": "eth_call", "params": [{"to": a, "data": "0xe75235b8"}, "latest"]})
    for r in batch(reqs) or []:
        j, kind = divmod(r.get("id", 0), 2)
        a = part[j]; d = res.setdefault(a, {})
        if kind == 0:
            d["code"] = len(r.get("result") or "0x") > 2
        else:
            v = r.get("result")
            d["safe"] = bool(v and v != "0x" and len(v) == 66 and 0 < int(v, 16) < 50)
    time.sleep(0.4)
json.dump(res, open(f"{SP}/work/struct.json", "w"))
c = collections.Counter()
for a in eff:
    d = res.get(a, {})
    c["safe" if d.get("safe") else ("contract" if d.get("code") else ("eoa" if "code" in d else "unknown"))] += 1
n = len(eff)
print({k: f"{v} ({v/n*100:.1f}%)" for k, v in c.most_common()})
