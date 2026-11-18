"""s167 area B, step 6: multi-hop origin for sample cases whose first inflow came from an EOA ('from_eoa' in genesis
sample): step back up to 3 more hops (largest inflow of the token to the current address within 7 days before its first
inflow), classify the final origin: mint / exchange / contract (with Blockscout tags) / EOA. Tenderly public RPC, 1.5 s pause."""
import json, re, time, urllib.request, collections
SP = "/home/user/mc_data/s168"
RPC = "https://gateway.tenderly.co/public/mainnet"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
CEX = json.load(open("/home/user/mc_data/s160/sets.json"))["cex"]
TOKS = {v["sym"]: k for k, v in json.load(open("/home/user/mc_data/s160/sets.json"))["toks"].items()}
BS = json.load(open(f"{SP}/work/bs_meta.json"))
DEP = re.compile(r"deposit|\bdep\b", re.I)
R = [r for r in json.load(open(f"{SP}/work/genesis_sample.json")) if r.get("cls") == "from_eoa"]
pad = lambda x: "0x" + "0" * 24 + x[2:]
def rpc(body):
    for k in range(5):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(RPC, data=json.dumps(body).encode(), headers=UA), timeout=90))
        except Exception:
            time.sleep(4 + 4 * k)
    return {}
def tags(a):
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request("https://metadata.services.blockscout.com/api/v1/metadata?chainId=1&addresses=" + a, headers={"User-Agent": "research-script/1.0"}), timeout=30))
        return [t["name"] for v in (d.get("addresses") or {}).values() for t in v.get("tags", [])]
    except Exception:
        return []
out = []
for r in R:
    tok = TOKS[r["sym"]]; cur = r["first_src"]; blk = r["first_block"]; path = [cur]; final = None
    for hop in range(3):
        if cur == "0x" + "0" * 40: final = "mint"; break
        if cur in CEX or any(DEP.search(t) for t in BS.get(cur, [])): final = "exchange"; break
        g = rpc({"jsonrpc": "2.0", "id": 1, "method": "eth_getCode", "params": [cur, "latest"]}); time.sleep(0.8)
        if len((g or {}).get("result") or "0x") > 2:
            final = "contract:" + ",".join(tags(cur)[:2]); break
        lg = rpc({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [{"fromBlock": hex(max(blk - 50400, 0)), "toBlock": hex(blk), "address": tok, "topics": [T0, None, pad(cur)]}]}); time.sleep(1.5)
        logs = (lg or {}).get("result")
        if not isinstance(logs, list) or not logs:
            final = "eoa_no_inflow_7d"; break
        tot = collections.Counter()
        for x in logs: tot["0x" + x["topics"][1][-40:]] += int(x["data"], 16) if x["data"] not in ("0x", "") else 0
        nxt = tot.most_common(1)[0][0]
        blk = min(int(x["blockNumber"], 16) for x in logs if "0x" + x["topics"][1][-40:] == nxt)
        cur = nxt; path.append(cur)
    if final is None: final = "eoa_after_3_hops"
    out.append(dict(sym=r["sym"], hops=len(path), final=final))
    print(r["sym"], len(path), final, flush=True)
json.dump(out, open(f"{SP}/work/multihop.json", "w"))
c = collections.Counter(o["final"].split(":")[0] for o in out); print("final origin", dict(c))
