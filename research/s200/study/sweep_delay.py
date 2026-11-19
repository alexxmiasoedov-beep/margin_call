"""s200 (изучение) — задержка между заводом держателя на адрес пополнения Binance и сметанием на горячий кошелёк.
Событие 🐋 (s182_origin.pkl: перевод frm → адрес Binance ≥ 0,5% обращения) — это, как правило, сметание с адреса
пополнения frm. Здесь — когда держатель завёл монеты на frm: последний входящий перевод того же токена на frm
до блока события (eth_getLogs через публичный RPC). Только время и суммы, без цен и доходов.
Запуск из /home/user/mc_data: python3 sweep_delay.py [число событий] [начало]"""
import json
import os
import sys
import time
import urllib.request

import numpy as np
import pandas as pd

OUT = "/home/user/mc_data"
CACHE = f"{OUT}/s200/sweep_cache.json"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
URLS = ["https://gateway.tenderly.co/public/mainnet", "https://rpc.mevblocker.io", "https://ethereum-rpc.publicnode.com"]
T0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def post(body, tries=6):
    for k in range(tries):
        try:
            req = urllib.request.Request(URLS[k % len(URLS)], data=json.dumps(body).encode(), headers=UA)
            r = json.loads(urllib.request.urlopen(req, timeout=60).read())
            if "error" not in r:
                return r
        except Exception:
            pass
        time.sleep(1 + 2 * k)
    return None


def incoming(tok, addr, block, span):
    """Входящие переводы tok на addr в [block − span, block]: [(блок, индекс, от, сумма в единицах)]."""
    topic = "0x" + "0" * 24 + addr[2:].lower()
    r = post({"jsonrpc": "2.0", "id": 1, "method": "eth_getLogs",
              "params": [{"fromBlock": hex(max(1, block - span)), "toBlock": hex(block), "address": tok,
                          "topics": [T0, None, topic]}]})
    if r is None:
        return None
    out = []
    for lg in r["result"]:
        out.append((int(lg["blockNumber"], 16), int(lg["logIndex"], 16), "0x" + lg["topics"][1][-40:],
                    int(lg["data"], 16) if lg["data"] not in ("0x", "") else 0))
    return out


def main(n=200, start=0):
    os.makedirs(f"{OUT}/s200", exist_ok=True)
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    E = pd.read_pickle(f"{OUT}/s182_origin.pkl").sort_values("t").reset_index(drop=True)
    idx = np.linspace(0, len(E) - 1, n).astype(int)[start:]       # равномерно по времени
    t0 = time.time()
    for k, i in enumerate(idx):
        r = E.iloc[i]
        key = f"{r.tok}:{r.frm}:{int(r.block)}"
        if key in cache:
            continue
        got = None
        for span in (7200, 50000):                                 # ~1 сут, затем ~7 сут
            got = incoming(r.tok, r.frm, int(r.block), span)
            if got is None or [g for g in got if g[0] < int(r.block) or g[1] < int(r.li)]:
                break
        cache[key] = got
        if k % 20 == 0:
            json.dump(cache, open(CACHE, "w"))
            print(f"{k}/{len(idx)} за {time.time() - t0:.0f} с", flush=True)
        time.sleep(0.15)
    json.dump(cache, open(CACHE, "w"))
    print("готово", len(cache))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200, int(sys.argv[2]) if len(sys.argv) > 2 else 0)
