"""s250 пилот гипотезы «раздача на свежие адреса»: все переводы 14 токенов (eth_getLogs публичных узлов без ключа; SQD Portal отдаёт ~850 блоков за запрос — медленно) за ~37 сут,
событие: адрес A за 6 ч отправил токен ≥ 10 разным получателям, которых не было в данных раньше (прогрев 7 сут), сумма ≥ 0,25% / 0,5% обращения,
A не биржа; отмечаем, получил ли A ≥ половины суммы одним переводом за 7 сут до (признак «блок → раздача»)."""
import json, time, urllib.request, collections, sys
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
URL = "https://portal.sqd.dev/datasets/ethereum-mainnet/stream"
T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
CEX = set(json.load(open("/home/user/mc_data/s160/sets.json"))["cex"])
tm = json.load(open("/home/user/mc_data/s160/tok_meta.json"))
TOKS = json.load(open("work/fan_tokens.json"))
B0, B1 = int(sys.argv[1]), int(sys.argv[2]); WARM = 7 * 7200
def stream(q):
    for k in range(30):
        try:
            r = urllib.request.urlopen(urllib.request.Request(URL, data=json.dumps(q).encode(), headers=UA), timeout=300).read().decode()
            return [json.loads(x) for x in r.splitlines() if x.strip()]
        except Exception:
            time.sleep(min(60, 5 + 5 * k))
    return None
RPC = ["https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet"]
KK = [0]
def getlogs(addrs, b0, b1, depth=0):
    q = {"fromBlock": hex(b0), "toBlock": hex(b1), "address": addrs, "topics": [T0]}
    for att in range(6):
        KK[0] += 1
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(RPC[KK[0] % 2], data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs", "params": [q]}).encode(), headers=UA), timeout=120))
            if isinstance(r.get("result"), list): return r["result"]
            msg = json.dumps(r.get("error"))
            if ("more than" in msg or "exceeds" in msg) and b1 > b0 and depth < 10:
                m = (b0 + b1) // 2
                a = getlogs(addrs, b0, m, depth + 1); b = getlogs(addrs, m + 1, b1, depth + 1)
                return None if a is None or b is None else a + b
        except Exception:
            pass
        time.sleep(2 + 2 * att)
    return None
ALL = {}
addrs = [t[0] for t in TOKS]
for s0 in range(B0, B1 + 1, 10000):
    res = getlogs(addrs, s0, min(s0 + 9999, B1))
    if res is None: print("fail", s0, flush=True); continue
    for l in res:
        ALL.setdefault(l["address"].lower(), []).append(l)
    time.sleep(0.3)
print("логи загружены", {k[:8]: len(v) for k, v in ALL.items()}, flush=True)
BT = {}
def bts(bn):
    # время блока: интерполяция по 12 с от B0 (для окон 6 ч и 7 сут точности хватает)
    return 1795000000 + (bn - B0) * 12
out = {}
for tok, sym, circ in TOKS:
    dec = int((tm.get(tok) or {}).get("decimals") or 18)
    logs = []
    for l in sorted(ALL.get(tok.lower(), []), key=lambda x: (int(x["blockNumber"], 16), int(x["logIndex"], 16))):
        if len(l["topics"]) < 3: continue
        v = int(l["data"], 16) / 10 ** dec if l["data"] not in ("0x", "") else 0
        bn = int(l["blockNumber"], 16)
        logs.append((bts(bn), bn, "0x" + l["topics"][1][-40:], "0x" + l["topics"][2][-40:], v))
    seen = set(); recv_big = collections.defaultdict(list)
    sent = collections.defaultdict(list)
    ev = []
    for ts, bn, f, t, v in logs:
        if bn < B0 + WARM:
            seen.add(t); seen.add(f)
            if v >= 0.0025 * circ: recv_big[t].append((ts, v))
            continue
        fresh = t not in seen
        seen.add(t)
        if v >= 0.0025 * circ: recv_big[t].append((ts, v))
        if f in CEX or f == "0x" + "0" * 40: continue
        sent[f].append((ts, t, v, fresh))
        # окно 6 ч
        w = [x for x in sent[f] if ts - x[0] <= 6 * 3600]
        sent[f] = w
        fr = {x[1] for x in w if x[3]}
        tot = sum(x[2] for x in w if x[3])
        if len(fr) >= 10 and tot >= 0.0025 * circ:
            if not ev or ev[-1][1] != f or ts - ev[-1][0] > 24 * 3600:
                big = any(ts - 7 * 86400 <= r0 <= ts and rv >= 0.5 * tot for r0, rv in recv_big.get(f, []))
                ev.append((ts, f, len(fr), round(tot / circ * 100, 3), big))
    days = (B1 - B0 - WARM) / 7200
    out[sym] = {"logs": len(logs), "days": days, "events": ev}
    e5 = [e for e in ev if e[3] >= 0.5]
    print(f"{sym:7s} логов {len(logs):>8} сут {days:.0f} событий ≥0,25%: {len(ev)}, ≥0,5%: {len(e5)}, из них «блок → раздача»: {sum(1 for e in ev if e[4])}", flush=True)
    for e in ev[:3]: print("     ", time.strftime("%Y-%m-%d %H:%M", time.gmtime(e[0])), e[1][:12], "получателей", e[2], f"{e[3]}%", "блок" if e[4] else "")
json.dump(out, open("work/fan_pilot.json", "w"))
