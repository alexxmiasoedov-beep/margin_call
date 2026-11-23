"""s250: частота переводов ≥ 0,1% обращения от «не бирж» на открытые адреса ММ (Ethereum, 261 токен s160) за ~24 мес.
Метки ММ — work/mm_labels_eth.json (Blockscout + eth-labels + etherscan-labels), без Alameda. Обращение — история CMC s160/circ по дате блока.
Публичные RPC без ключа (MEV Blocker, Tenderly), шаг 20 тыс. блоков. Выход: work/mm_scan24.json"""
import json, sys, time, urllib.request, collections, bisect
a0, a1 = int(sys.argv[1]), int(sys.argv[2])
RPC = ["https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet"]
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
S = json.load(open("/home/user/mc_data/s160/sets.json")); TOK = S["toks"]; CEX = set(S["cex"])
MMall = json.load(open("work/mm_labels_eth.json"))
MM = {a: v for a, v in MMall.items() if v[0] != "alameda" and a != "0x51c72848c68a965f66fa7a88855f9f7784502a7f"}  # без RFQ-контракта Wintermute (сделки DEX)
STABLE = {"USDC", "USDT", "XAUT", "PAXG", "FDUSD", "TUSD", "DAI", "USDE", "USD1", "BUSD", "EUR", "EURI", "USDP"}
TOK = {t: v for t, v in TOK.items() if v["perp"] not in STABLE}
tm = json.load(open("/home/user/mc_data/s160/tok_meta.json"))
DEC = {t: int((tm.get(t) or {}).get("decimals") or 18) for t in TOK}
IDS = json.load(open("/home/user/mc_data/s160/cmc_ids.json"))
CIRC = {}
for t in TOK:
    try:
        rows = json.load(open(f"/home/user/mc_data/s160/circ/{IDS[t]['id']}.json"))
        rows = [r for r in rows if r[1] and r[1] > 0]
        CIRC[t] = ([r[0] for r in rows], [float(r[1]) for r in rows])
    except Exception:
        CIRC[t] = ([], [])
BT = {int(k): v for k, v in json.load(open("/home/user/mc_data/s160/cache_blocktime.json")).items()}
bks = sorted(BT)
def btime(b):
    i = bisect.bisect_right(bks, b) - 1
    if i < 0: return BT[bks[0]]
    if i + 1 < len(bks):
        b0, b1 = bks[i], bks[i + 1]; return BT[b0] + (BT[b1] - BT[b0]) * (b - b0) / (b1 - b0)
    return BT[bks[i]] + (b - bks[i]) * 12
def circ(t, ts):
    d, v = CIRC[t]
    if not d: return float(TOK[t].get("circ") or 0)
    day = time.strftime("%Y-%m-%d", time.gmtime(ts))
    i = bisect.bisect_right(d, day) - 1
    return v[max(i, 0)]
pad = lambda x: "0x" + "0" * 24 + x[2:]
mm_topics = [pad(x) for x in MM]
rows = []; step = 10000; k = 0; fails = []
def getlogs(b0, b1, depth=0):
    global k
    q = {"fromBlock": hex(b0), "toBlock": hex(b1), "address": list(TOK), "topics": [T0, None, mm_topics]}
    for att in range(6):
        k += 1
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(RPC[k % 2], data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [q]}).encode(), headers=UA), timeout=120))
            if isinstance(r.get("result"), list): return r["result"]
            msg = json.dumps(r.get("error"))
            if ("more than" in msg or "exceeds" in msg) and b1 > b0 and depth < 8:
                m = (b0 + b1) // 2
                a = getlogs(b0, m, depth + 1); b = getlogs(m + 1, b1, depth + 1)
                return None if a is None or b is None else a + b
        except Exception:
            pass
        time.sleep(2 + 2 * att)
    return None
for s in range(a0, a1, step):
    e = min(s + step - 1, a1)
    res = getlogs(s, e)
    if res is None:
        fails.append(s); print("fail", s, flush=True); continue
    for x in res:
        tok = x["address"].lower(); frm = "0x" + x["topics"][1][-40:]; to = "0x" + x["topics"][2][-40:]
        if tok not in TOK or to not in MM: continue
        if frm in CEX or frm in MMall or frm == "0x" + "0" * 40: continue
        v = int(x["data"], 16) / 10 ** DEC.get(tok, 18) if x["data"] not in ("0x", "") else 0
        b = int(x["blockNumber"], 16); ts = btime(b); c = circ(tok, ts)
        if c > 0 and v >= 0.001 * c:
            rows.append([b, int(ts), TOK[tok]["perp"], tok, frm, to, MM[to][0], round(v / c * 100, 3), x["transactionHash"]])
    if (s - a0) // step % 50 == 0: print("progress", s, len(rows), flush=True)
    time.sleep(0.3)
json.dump({"rows": rows, "fails": fails, "a0": a0, "a1": a1}, open("work/mm_scan24.json", "w"))
print("done", len(rows), "fails", len(fails))
