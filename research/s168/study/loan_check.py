"""s167 area A: validate on-chain visibility of documented DAO market-maker loans. For a token and block window, list
transfers >= min amount with recipient tags from Blockscout metadata. Usage: python3 -I loan_check.py <token> <from> <to> <min>"""
import json, sys, time, urllib.request
tok, a, b, mn = sys.argv[1].lower(), int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
RPC = ["https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet"]
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
logs = []
for s in range(a, b, 100000):
    q = {"fromBlock": hex(s), "toBlock": hex(min(s + 99999, b)), "address": tok, "topics": [T0]}
    for k in range(5):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(RPC[k % 2], data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [q]}).encode(), headers=UA), timeout=120))
            if isinstance(r.get("result"), list): logs += r["result"]; break
        except Exception: pass
        time.sleep(3 + 3 * k)
    time.sleep(1.0)
big = []
for x in logs:
    v = int(x["data"], 16) / 1e18 if x["data"] not in ("0x", "") else 0
    if v >= mn: big.append((int(x["blockNumber"], 16), "0x" + x["topics"][1][-40:], "0x" + x["topics"][2][-40:], round(v)))
addrs = sorted({y for r in big for y in r[1:3]})
tags = {}
for i in range(0, len(addrs), 40):
    u = "https://metadata.services.blockscout.com/api/v1/metadata?chainId=1&addresses=" + ",".join(addrs[i:i + 40])
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "research-script/1.0"}), timeout=40))
        tags.update({k.lower(): [t["name"] for t in v.get("tags", [])][:2] for k, v in (d.get("addresses") or {}).items()})
    except Exception: pass
    time.sleep(0.5)
print("logs", len(logs), "big", len(big))
for blk, f, t, v in big[:40]:
    print(blk, f[:10], tags.get(f, []), "->", t[:10], tags.get(t, []), v)
