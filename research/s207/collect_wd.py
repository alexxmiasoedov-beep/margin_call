"""s207 — выводы с Binance: все переводы ERC-20 токенов с перпом Binance (261 токен, s160/sets.json) С адресов Binance
(150 адресов с первой меткой «Binance» из сбора s160) через публичные RPC Ethereum (eth_getLogs, Tenderly и MEV Blocker, без
ключа), блоки 10 950 000 (≈ 28.09.2020) — последний. Сразу оставляются переводы ≥ 0,05% нынешнего обращения монеты.
Файлы по 100 тыс. блоков — s207/raw/b<начало>.json.gz: [блок, токен, от, кому, сумма, tx, logIndex]. Два потока,
прерванный сбор продолжается. Запуск из /home/user/mc_data: python3 <repo>/research/s207/collect_wd.py [rev]"""
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
URLS = ["https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io"]
S = json.load(open("s160/sets.json"))
CEX = [a for a, v in S["cex"].items() if v and v[0] == "Binance"]; TOKS = list(S["toks"].keys())
META = json.load(open("s160/tok_meta.json"))
DEC = {t: int((META.get(t) or {}).get("decimals") or 18) for t in TOKS}
MIN = {t: 0.0005 * float(S["toks"][t].get("circ") or 0) for t in TOKS}
CHUNKS = [CEX[i:i + 1000] for i in range(0, len(CEX), 1000)]
FIRST, STEP_FILE, STEP = 10_950_000, 100_000, 10_000


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def rpc(url, method, params, timeout=90):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=UA), timeout=timeout) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, f"EXC {type(e).__name__}"
    return d.get("result"), d.get("error")


def fetch(a, b, ch, k0=0):
    q = {"fromBlock": hex(a), "toBlock": hex(b), "address": TOKS, "topics": [T0, [pad(x) for x in ch], None]}
    for attempt in range(8):
        r, e = rpc(URLS[(attempt + k0) % 2], "eth_getLogs", [q])
        if isinstance(r, list):
            return r
        es = str(e).lower()
        if ("more than" in es or "limit" in es or "too many" in es or "exceed" in es) and b > a:
            m = (a + b) // 2
            return fetch(a, m, ch, k0) + fetch(m + 1, b, ch, k0)
        time.sleep(2 + 3 * attempt)
    raise RuntimeError(f"{a}-{b}: {e}")


def one(start, k0):
    path = f"s207/raw/b{start}.json.gz"
    if os.path.exists(path):
        return start, None
    rows = []
    for s in range(start, start + STEP_FILE, STEP):
        e = s + STEP - 1
        for ch in CHUNKS:
            for x in fetch(s, e, ch, k0):
                tok = x["address"].lower()
                v = int(x["data"], 16) if x["data"] not in ("0x", "") else 0
                amt = v / 10 ** DEC.get(tok, 18)
                if amt >= MIN.get(tok, float("inf")) > 0:
                    rows.append([int(x["blockNumber"], 16), tok, "0x" + x["topics"][1][-40:], "0x" + x["topics"][2][-40:], amt,
                                 x["transactionHash"], int(x["logIndex"], 16)])
        time.sleep(0.1)
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt") as f:
        json.dump(rows, f)
    os.replace(tmp, path)
    return start, len(rows)


def main():
    os.makedirs("s207/raw", exist_ok=True)
    last, _ = rpc(URLS[0], "eth_blockNumber", [])
    last = int(last, 16)
    starts = list(range(FIRST, last - STEP_FILE, STEP_FILE))
    if "rev" in sys.argv[1:]:                      # второй процесс идёт с конца навстречу первому
        starts = starts[::-1]
    print("файлов", len(starts), "до блока", last, flush=True)
    t = time.time(); n = 0
    with ThreadPoolExecutor(2) as ex:
        for st, k in ex.map(lambda p: one(p[1], p[0] % 2), enumerate(starts)):
            n += 1
            if k is not None and n % 5 == 0:
                print(n, "из", len(starts), "блок", st, "строк", k, f"{time.time() - t:.0f} с", flush=True)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
