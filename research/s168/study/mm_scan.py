"""s167 area A: frequency probe — ERC-20 transfers of the 261 s160 tokens TO market-maker / OTC addresses (Blockscout tags,
work/mm_addrs.json, without Alameda) from non-exchange senders, amount >= 0.5% of current circulating supply (sets.json),
over a block window. Public RPC without key (MEV Blocker), 20k-block steps, 1 s pause.
Usage: python3 -I mm_scan.py <from_block> <to_block> <out.json>"""
import json, sys, time, urllib.request, collections
a0, a1, outp = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
RPC = ["https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet"]
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
S = json.load(open("/home/user/mc_data/s160/sets.json")); TOK = S["toks"]; CEX = S["cex"]
META = json.load(open("/home/user/mc_data/s160/tok_meta.json")) if False else {}
MM = json.load(open("work/mm_core.json"))
pad = lambda x: "0x" + "0" * 24 + x[2:]
# decimals: reuse s160 tok_meta if present
try:
    tm = json.load(open("/home/user/mc_data/s160/tok_meta.json")); DEC = {t: int((tm.get(t) or {}).get("decimals") or 18) for t in TOK}
except Exception:
    DEC = {t: 18 for t in TOK}
MIN = {t: 0.005 * float(TOK[t].get("circ") or 0) for t in TOK}
rows = []; step = 20000; k = 0
for s in range(a0, a1, step):
    e = min(s + step - 1, a1)
    q = {"fromBlock": hex(s), "toBlock": hex(e), "address": list(TOK), "topics": [T0, None, [pad(x) for x in MM]]}
    res = None
    for att in range(6):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(RPC[(att + k) % 2], data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [q]}).encode(), headers=UA), timeout=90))
            if isinstance(r.get("result"), list):
                res = r["result"]; break
        except Exception:
            pass
        time.sleep(3 + 3 * att)
    k += 1
    if res is None:
        print("fail", s, e, flush=True); continue
    for x in res:
        tok = x["address"].lower(); frm = "0x" + x["topics"][1][-40:]; to = "0x" + x["topics"][2][-40:]
        v = int(x["data"], 16) / 10 ** DEC.get(tok, 18) if x["data"] not in ("0x", "") else 0
        if v >= MIN.get(tok, float("inf")) > 0 and frm not in CEX and frm not in MM and frm != "0x" + "0" * 40:
            rows.append([int(x["blockNumber"], 16), TOK[tok]["sym"], frm, to, MM[to], round(v / float(TOK[tok]["circ"]) * 100, 2), x["transactionHash"]])
    time.sleep(1.0)
json.dump(rows, open(outp, "w"))
print("blocks", a0, a1, "transfers >=0.5% circ from non-CEX/non-MM to MM:", len(rows))
print(collections.Counter(r[4].split(":")[0].split("(")[0].strip() for r in rows).most_common(10))
print(collections.Counter(r[1] for r in rows).most_common(15))
