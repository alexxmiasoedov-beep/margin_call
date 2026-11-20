"""s244 — переводы токенов фьючерсов Binance в сети Arbitrum на адреса Binance из меток (bot/cex_labels.tsv) за 01.10.2024–
20.10.2026: официальный узел arb1.arbitrum.io без ключа, eth_getLogs по 10 тыс. блоков (все токены и адреса Binance одним
запросом). Сохраняются переводы от «не бирж» (отправитель не в метках бирж и не 0x0) на сумму > 0 вместе с временем блока
(по краям куска; внутри — линейно). Куски по 500 тыс. блоков — s244/raw/<начальный блок>.json, готовые пропускаются.
Запуск из /home/user/mc_data: python3 <repo>/research/s244/collect_arb.py [потоков]"""
import json
import os
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
URL = "https://arb1.arbitrum.io/rpc"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
TR = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
CH, STEP = 500_000, 10_000
SKIP = {"ETH", "USDC", "USDT"}


def rpc(m, p):
    err = None
    for k in range(8):
        try:
            req = urllib.request.Request(URL, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
                                         headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                j = json.loads(r.read())
            if "result" in j:
                return j["result"]
            err = str(j.get("error"))[:200]
        except Exception as e:
            err = str(e)[:200]
        time.sleep(min(60, 2 * 2 ** k))
    raise RuntimeError(err)


def ts(b):
    return int(rpc("eth_getBlockByNumber", [hex(b), False])["timestamp"], 16)


def block_at(t):
    lo, hi = 1, int(rpc("eth_blockNumber", []), 16)
    while hi - lo > 1:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if ts(mid) < t else (lo, mid)
    return hi


def labels():
    cex, binance = set(), []
    for ln in open(os.path.join(HERE, "..", "..", "bot", "cex_labels.tsv"), encoding="utf-8"):
        p = ln.rstrip("\n").split("\t")
        if len(p) >= 2 and p[0].startswith("0x") and len(p[0]) == 42:
            cex.add(p[0].lower())
            if p[1] == "Binance":
                binance.append(p[0].lower())
    return cex, binance


def main():
    nthr = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    nets = json.load(open("s242/perp_nets.json"))
    toks = {a.lower(): c for c, a, eth, bsc, ins in nets["ARBITRUM"] if a and c not in SKIP}
    cex, binance = labels()
    pad = ["0x" + "0" * 24 + a[2:] for a in sorted(set(binance))]
    os.makedirs("s244/raw", exist_ok=True)
    mp = "s244/meta.json"
    if os.path.exists(mp):
        M = json.load(open(mp)); B0, B1 = M["B0"], M["B1"]
    else:
        B0, B1 = block_at(1727740800), block_at(1792540800)
        json.dump({"tokens": toks, "binance": sorted(set(binance)), "B0": B0, "B1": B1}, open(mp, "w"))
    todo = [b for b in range(B0, B1, CH) if not os.path.exists(f"s244/raw/{b}.json")]
    print(f"токенов {len(toks)}, адресов Binance {len(set(binance))}, блоки {B0}–{B1}, кусков {len(todo)}", flush=True)
    lock = threading.Lock(); t0 = time.time(); done = [0]

    def work():
        while True:
            with lock:
                if not todo:
                    return
                b = todo.pop(0)
            e = min(b + CH, B1) - 1
            tb, te = ts(b), ts(e)
            rows = []
            for lo in range(b, e + 1, STEP):
                hi = min(lo + STEP - 1, e)
                for lg in rpc("eth_getLogs", [{"fromBlock": hex(lo), "toBlock": hex(hi), "address": list(toks),
                                               "topics": [TR, None, pad]}]):
                    fr = "0x" + lg["topics"][1][-40:]
                    if fr in cex or fr == "0x" + "0" * 40 or lg["data"] in ("0x", "0x" + "0" * 64):
                        continue
                    bn = int(lg["blockNumber"], 16)
                    rows.append([bn, tb + (te - tb) * (bn - b) / max(1, e - b), lg["address"].lower(), fr,
                                 "0x" + lg["topics"][2][-40:], lg["data"], lg["transactionHash"]])
            json.dump(rows, open(f"s244/raw/{b}.json.tmp", "w"))
            os.replace(f"s244/raw/{b}.json.tmp", f"s244/raw/{b}.json")
            with lock:
                done[0] += 1
                if done[0] % 20 == 0:
                    print(f"готово {done[0]} кусков, осталось {len(todo)}, {(time.time() - t0) / 60:.1f} мин", flush=True)

    th = [threading.Thread(target=work) for _ in range(nthr)]
    for x in th:
        x.start()
    for x in th:
        x.join()
    print("сбор окончен", flush=True)


if __name__ == "__main__":
    main()
