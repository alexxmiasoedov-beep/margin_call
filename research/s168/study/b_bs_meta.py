"""s167: Blockscout metadata tags (no key) for distinct senders and upstream sources of the large-deposit events.
Batches of 40 addresses, 0.5 s pause, resumable. Output work/bs_meta.json {addr: [tag names]}"""
import json, os, time, urllib.request
SP = "/home/user/mc_data/s168"
UA = {"User-Agent": "research-script/1.0"}
ev = json.load(open(f"{SP}/work/b_events.json"))
hop = json.load(open("/home/user/mc_data/s160/cache_hop.json"))
CEX = json.load(open("/home/user/mc_data/s160/sets.json"))["cex"]
addrs = set()
for e in ev:
    addrs.add(e["frm"])
    h = hop.get(f"{e['tok']}:{e['frm']}:{e['block']}")
    if h and h[0] and h[0] not in CEX:
        addrs.add(h[0])
out = f"{SP}/work/bs_meta.json"
M = json.load(open(out)) if os.path.exists(out) else {}
todo = sorted(a for a in addrs if a not in M)
print("addresses", len(addrs), "todo", len(todo), flush=True)
for i in range(0, len(todo), 40):
    part = todo[i:i + 40]
    url = "https://metadata.services.blockscout.com/api/v1/metadata?chainId=1&addresses=" + ",".join(part)
    for k in range(4):
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40)); break
        except Exception as e:
            d = None; time.sleep(3 + 3 * k)
    if d is None:
        continue
    got = {a.lower(): [t["name"] for t in v.get("tags", [])] for a, v in (d.get("addresses") or {}).items()}
    for a in part:
        M[a] = got.get(a, [])
    if (i // 40) % 25 == 0:
        json.dump(M, open(out, "w")); print("done", i + len(part), flush=True)
    time.sleep(0.5)
json.dump(M, open(out, "w")); print("saved", len(M), "with tags", sum(1 for v in M.values() if v))
