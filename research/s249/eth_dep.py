"""Адреса пополнения Binance по свежим сметаниям в Ethereum (переводы токенов на горячий кошелёк 0x690c…)."""
import json, sys, time, urllib.request
RPC = "https://mainnet.gateway.tenderly.co"
T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
HOT = "0x690c3eebf6ee237f00fc96f9766282f096c191cc"
def rpc(m, p):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode()
    for k in range(6):
        try:
            r = urllib.request.Request(RPC, data=body, headers={"Content-Type": "application/json", "User-Agent": "research-script/1.0"})
            j = json.loads(urllib.request.urlopen(r, timeout=60).read())
            if "result" in j: return j["result"]
            print("err", j.get("error")); time.sleep(3)
        except Exception as e:
            print("exc", e); time.sleep(3)
head = int(rpc("eth_blockNumber", []), 16)
deps = {}
for lo in range(head - 3000, head, 500):
    L = rpc("eth_getLogs", [{"fromBlock": hex(lo), "toBlock": hex(min(lo + 499, head)), "topics": [T, None, "0x" + "0" * 24 + HOT[2:]]}]) or []
    for l in L:
        deps["0x" + l["topics"][1][-40:]] = deps.get("0x" + l["topics"][1][-40:], 0) + 1
print("адресов пополнения:", len(deps))
json.dump(sorted(deps), open("eth_deps.json", "w"))
