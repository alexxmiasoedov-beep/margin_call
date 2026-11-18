"""s167: CoW Protocol ComposableCoW conditional orders (TWAP etc.) on Ethereum — how often a perp token (s160 set) is the
sell token. Event ConditionalOrderCreated(owner indexed, (handler, salt, staticInput)). Public RPC, block chunks of 500k."""
import json, time, urllib.request, collections, datetime as dt
RPC = ["https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet"]
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
CC = "0xfdafc9d1902f4e0b84f65f49f244b32b31013b74"
TOPIC = "0x2cceac5555b0ca45a3744ced542f54b56ad2eb45e521962372eef212a2cbf361"
TWAP_H = "0x6cf1e9ca41f7611def408122793c358a3d11e5a5"
S = json.load(open("/home/user/mc_data/s160/sets.json")); TOK = S["toks"]
tm = json.load(open("/home/user/mc_data/s160/tok_meta.json"))
logs = []
for a in range(17800000, 26450000, 500000):
    q = {"fromBlock": hex(a), "toBlock": hex(min(a + 499999, 26450000)), "address": CC, "topics": [TOPIC]}
    for k in range(6):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(RPC[k % 2], data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [q]}).encode(), headers=UA), timeout=120))
            if isinstance(r.get("result"), list):
                logs += r["result"]; break
        except Exception:
            pass
        time.sleep(4 + 4 * k)
    time.sleep(1.5)
print("ConditionalOrderCreated logs", len(logs))
rows = []
for x in logs:
    d = bytes.fromhex(x["data"][2:])
    w = lambda i: d[32 * i:32 * i + 32]
    handler = "0x" + w(1)[-20:].hex()
    blen = int.from_bytes(w(4), "big"); si = d[32 * 5:32 * 5 + blen]
    if handler != TWAP_H or len(si) < 320:
        rows.append(("other", None)); continue
    sell = "0x" + si[12:32].hex(); buy = "0x" + si[44:64].hex()
    part = int.from_bytes(si[96:128], "big"); n = int.from_bytes(si[192:224], "big"); t = int.from_bytes(si[224:256], "big")
    rows.append(("twap", (int(x["blockNumber"], 16), sell, buy, part, n, t, "0x" + x["topics"][1][-40:], x["transactionHash"])))
tw = [r[1] for r in rows if r[0] == "twap"]
print("TWAP orders", len(tw), "other handlers", sum(1 for r in rows if r[0] == "other"))
ours = [r for r in tw if r[1] in TOK]
print("TWAP sells of perp tokens", len(ours))
c = collections.Counter(TOK[r[1]]["sym"] for r in ours); print(c.most_common(20))
big = []
for b, sell, buy, part, n, t, own, txh in ours:
    dec = int((tm.get(sell) or {}).get("decimals") or 18)
    tot = part * n / 10 ** dec; frac = tot / float(TOK[sell]["circ"] or 1)
    big.append((b, TOK[sell]["sym"], round(frac * 100, 3), n, t))
json.dump(ours, open("work/cow_twap_ours.json", "w"))
print("with total >= 0.1% of current circ:", sum(1 for x in big if x[2] >= 0.1), [x for x in big if x[2] >= 0.1][:15])
