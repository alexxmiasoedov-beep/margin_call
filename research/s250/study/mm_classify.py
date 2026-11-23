"""Классы отправителей для переводов «не биржа → ММ» (work/mm_scan24.json): пул DEX, Safe, иной контракт, EOA; метки eth-labels и казначейства DefiLlama.
Публичный RPC без ключа (eth_getCode, eth_call). Итог — частоты в месяц по порогам и классам."""
import json, time, urllib.request, collections, csv
RPC = ["https://ethereum-rpc.publicnode.com", "https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet"]
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
def rpc(method, params, k=0):
    for att in range(5):
        try:
            r = json.load(urllib.request.urlopen(urllib.request.Request(RPC[(att + k) % 3], data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode(), headers=UA), timeout=40))
            if "result" in r: return r["result"]
            if "error" in r and att >= 1: return None
        except Exception:
            time.sleep(1 + att)
    return None
D = json.load(open("work/mm_scan24.json")); R = D["rows"]
lab = {}
for r in csv.reader(open("/home/user/mc_data/s168/dl/ethl_accounts.csv", encoding="utf-8", errors="ignore")):
    if len(r) >= 4 and r[1] == "1": lab.setdefault(r[0].lower(), f"{r[2]}|{r[3]}")
try:
    tre = json.load(open("/home/user/mc_data/s168/work/llama_treasury.json"))
    tre = {a.lower(): v for a, v in (tre.items() if isinstance(tre, dict) else [(x, "treasury") for x in tre])}
except Exception:
    tre = {}
senders = sorted({r[4] for r in R})
cls = {}
SEL = {"token0": "0x0dfe1681", "fee": "0xddca3f43", "getThreshold": "0xe75235b8", "getPoolId": "0x38fff2d0"}
for i, a in enumerate(senders):
    code = rpc("eth_getCode", [a, "latest"], i)
    if not code or code == "0x":
        c = "EOA"
    else:
        c = "контракт"
        if rpc("eth_call", [{"to": a, "data": SEL["getThreshold"]}, "latest"], i) not in (None, "0x"):
            c = "Safe"
        elif rpc("eth_call", [{"to": a, "data": SEL["token0"]}, "latest"], i) not in (None, "0x"):
            c = "пул DEX"
        elif rpc("eth_call", [{"to": a, "data": SEL["getPoolId"]}, "latest"], i) not in (None, "0x"):
            c = "пул DEX"
    l = lab.get(a, ""); 
    if a in tre: l = "treasury|" + str(tre[a])[:40]
    if any(k in l.lower() for k in ("uniswap", "sushiswap", "1inch", "0x:", "0x-protocol", "balancer", "curve", "paraswap", "kyber", "cow", "dex")): c = "пул DEX"
    cls[a] = (c, l)
    time.sleep(0.15)
json.dump(cls, open("work/mm_classify.json", "w"))
span_m = (max(r[1] for r in R) - min(r[1] for r in R)) / 86400 / 30.4 if R else 1
print("переводов ≥0,1%:", len(R), "за", round(span_m, 1), "мес; отправителей", len(senders))
for thr in (0.1, 0.5):
    S = [r for r in R if r[7] >= thr]
    c1 = collections.Counter(cls[r[4]][0] for r in S)
    print(f"\n≥{thr}% обращения: {len(S)} ({len(S)/span_m:.1f}/мес); классы отправителя: {dict(c1)}")
    nd = [r for r in S if cls[r[4]][0] != "пул DEX"]
    print(f"  без пулов DEX: {len(nd)} ({len(nd)/span_m:.1f}/мес); по ММ: {collections.Counter(r[6] for r in nd).most_common()}")
    nd2 = [r for r in nd if r[6] not in ("falconx", "cumberland", "genesis", "b2c2", "galaxy")]
    print(f"  без пулов DEX и без OTC/прайм (FalconX, Cumberland, Genesis, B2C2, Galaxy): {len(nd2)} ({len(nd2)/span_m:.1f}/мес); монет {len({r[2] for r in nd2})}")
    # одно событие на монету за 7 сут
    ev = []; last = {}
    for r in sorted(nd2, key=lambda x: x[1]):
        if r[2] in last and r[1] - last[r[2]] < 7 * 86400: continue
        last[r[2]] = r[1]; ev.append(r)
    print(f"  событий (монета, 7 сут): {len(ev)} ({len(ev)/span_m:.1f}/мес)")
    ins = [r for r in nd2 if cls[r[4]][0] in ("Safe", "контракт") or cls[r[4]][1]]
    print(f"  из них отправитель Safe/контракт/с меткой: {len(ins)} ({len(ins)/span_m:.1f}/мес)")
    for r in sorted(nd2, key=lambda x: -x[7])[:12]:
        print("   ", time.strftime("%Y-%m-%d", time.gmtime(r[1])), r[2], r[6], f"{r[7]}%", cls[r[4]][0], cls[r[4]][1][:50], r[4][:10])
