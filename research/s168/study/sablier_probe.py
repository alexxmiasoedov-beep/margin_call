"""s167: frequency probe — Sablier Lockup withdrawals (WithdrawFromLockupStream, asset indexed) of the 261 s160 tokens on
Ethereum over a block range, via a public RPC without key. Usage: python3 -I sablier_probe.py <rpc> <from> <to> <step>"""
import json, sys, time, urllib.request, collections
rpc, a, b, step = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
S = json.load(open("/home/user/mc_data/s160/sets.json")); T = S["toks"]
pad = lambda x: "0x" + "0" * 24 + x[2:]
topic0 = "0x40b88e5c41c5a97ffb7b6ef88a0a2d505aa0c634cf8a0275cb236ea7dd87ed4d"
out = []
for s in range(a, b, step):
    e = min(s + step - 1, b)
    q = {"fromBlock": hex(s), "toBlock": hex(e), "topics": [topic0, None, None, [pad(t) for t in T]]}
    body = {"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [q]}
    for k in range(4):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(rpc, data=json.dumps(body).encode(), headers=UA), timeout=60)); break
        except Exception as ex:
            r = {"error": str(ex)}; time.sleep(3 + 3 * k)
    if "result" not in r:
        print("err", s, e, str(r.get("error"))[:200]); continue
    out += r["result"]; time.sleep(0.5)
c = collections.Counter("0x" + x["topics"][3][-40:] for x in out)
print("withdrawals", len(out), "contracts", len({x['address'] for x in out}), "tokens", len(c))
for tok, n in c.most_common(15):
    print("  ", T[tok]["sym"], n)
json.dump(out, open("work/sablier_probe.json", "w"))
