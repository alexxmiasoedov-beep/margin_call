"""s181 — все переводы 261 ERC-20 токена с перпом (s160/sets.json) С адресов казначейств DefiLlama-Adapters (строгий список
владельцев, dla_parse.py; без адресов бирж и токенов) через публичный RPC Ethereum без ключа (eth_getLogs: Tenderly,
куски до 50 тыс. блоков с делением пополам; MEV Blocker — для кусков ≤ 10 тыс.). Блоки 10 950 000 (≈ 28.09.2020) —
последний. Файлы по 500 тыс. блоков — /home/user/mc_data/s181/out/b<начало>.json.gz: [блок, токен, от, кому, сумма, tx].
Прерванный сбор продолжается. Только сбор; доходы не считаются."""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common181 as C  # noqa: E402

UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
TEN, MEV = "https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io"
S = json.load(open(f"{C.D}/s160/sets.json"))
TOKS = list(S["toks"].keys())
META = json.load(open(f"{C.D}/s160/tok_meta.json"))
DEC = {t: int((META.get(t) or {}).get("decimals") or 18) for t in TOKS}
OWN = sorted({a for r in json.load(open(f"{C.OUT}/dla_treasury.json")) for a in r["owners"]} - set(S["cex"]) - set(TOKS))
OUTD = f"{C.OUT}/out"
FIRST, FILE, STEP = 10_950_000, 500_000, 50_000


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def rpc(url, method, params, timeout=120):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=UA), timeout=timeout) as r:
            d = json.load(r)
    except Exception as e:
        return None, f"{type(e).__name__} {str(e)[:80]}"
    return d.get("result"), d.get("error")


def fetch(a, b):
    q = {"fromBlock": hex(a), "toBlock": hex(b), "address": TOKS, "topics": [T0, [pad(x) for x in OWN], None]}
    e = None
    for k in range(6):
        url = MEV if (b - a < 10_000 and k % 2 == 1) else TEN
        r, e = rpc(url, "eth_getLogs", [q])
        if isinstance(r, list):
            return r
        es = str(e).lower()
        if ("more than" in es or "limit" in es or "exceed" in es or "too many" in es) and b > a:
            m = (a + b) // 2
            return fetch(a, m) + fetch(m + 1, b)
        time.sleep(3 + 5 * k)
    raise RuntimeError(f"{a}-{b}: {e}")


def main():
    os.makedirs(OUTD, exist_ok=True)
    last, _ = rpc(TEN, "eth_blockNumber", [])
    last = int(last, 16) - 10
    starts = list(range(FIRST, last, FILE))
    print(f"владельцев {len(OWN)}, токенов {len(TOKS)}, файлов {len(starts)} до блока {last}", flush=True)
    t0 = time.time()
    for n, st in enumerate(starts):
        path = f"{OUTD}/b{st}.json.gz"
        end = min(st + FILE, last)
        if os.path.exists(path) and end == st + FILE:
            continue
        rows = []
        for s in range(st, end, STEP):
            for x in fetch(s, min(s + STEP, end) - 1):
                tok = x["address"].lower()
                v = int(x["data"], 16) if x["data"] not in ("0x", "") else 0
                rows.append([int(x["blockNumber"], 16), tok, "0x" + x["topics"][1][-40:], "0x" + x["topics"][2][-40:],
                             v / 10 ** DEC.get(tok, 18), x["transactionHash"]])
            time.sleep(0.3)
        C.jsave(rows, path)
        print(f"{n + 1}/{len(starts)} блок {st} строк {len(rows)} {time.time() - t0:.0f} с", flush=True)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
