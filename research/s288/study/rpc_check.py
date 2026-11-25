"""s288 — проверка времени блока в архиве Whale Alert по публичным узлам без ключа (выборка по годам и цепям):
Ethereum — rpc.mevblocker.io (eth_getTransactionByHash отдаёт blockTimestamp), запасной — mainnet.gateway.tenderly.co
+ eth_getBlockByNumber; Bitcoin — mempool.space; Tron — api.trongrid.io; XRP — xrplcluster.com. Не чаще ~1 запроса в
секунду на узел, пауза и повтор при сбоях.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s288/study/rpc_check.py → s288/rpc_check.csv"""
import json
import os
import sys
import time
import urllib.request

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common288 as C  # noqa: E402

UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
last = {}


def call(url, body=None, host=None, tries=4):
    h = host or url.split("/")[2]
    for k in range(tries):
        w = 1.1 - (time.time() - last.get(h, 0))
        if w > 0:
            time.sleep(w)
        last[h] = time.time()
        try:
            req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, headers=UA)
            return json.loads(urllib.request.urlopen(req, timeout=40).read())
        except Exception as e:  # noqa: BLE001
            time.sleep(3 * (k + 1))
    return None


def eth(hashes):
    out = {}
    for i in range(0, len(hashes), 10):
        part = hashes[i:i + 10]
        r = call("https://rpc.mevblocker.io",
                 [{"jsonrpc": "2.0", "id": j, "method": "eth_getTransactionByHash", "params": [h]} for j, h in enumerate(part)])
        for x in r or []:
            res = x.get("result") or {}
            if res.get("blockTimestamp"):
                out[part[x["id"]]] = int(res["blockTimestamp"], 16)
            elif res.get("blockNumber"):
                b = call("https://mainnet.gateway.tenderly.co", {"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber",
                                                                  "params": [res["blockNumber"], False]})
                if b and b.get("result"):
                    out[part[x["id"]]] = int(b["result"]["timestamp"], 16)
    return out


def btc(h):
    r = call(f"https://mempool.space/api/tx/{h}/status")
    return r.get("block_time") if r else None


def tron(h):
    r = call("https://api.trongrid.io/wallet/gettransactioninfobyid", {"value": h})
    return r["blockTimeStamp"] / 1000 if r and r.get("blockTimeStamp") else None


def xrp(h):
    r = call("https://xrplcluster.com/", {"method": "tx", "params": [{"transaction": h, "binary": False}]})
    d = ((r or {}).get("result") or {}).get("date")
    return d + 946684800 if d else None


def main():
    A = pd.read_pickle(f"{C.OUT}/wa_archive.pkl.gz")
    A["y"] = pd.to_datetime(A.tb, unit="s").dt.year
    rng = np.random.default_rng(288)
    picks = []
    for ch, n in (("ethereum", 10), ("bitcoin", 6), ("tron", 4), ("ripple", 4)):
        for y, g in A[(A.chain == ch) & A.hash.str.len().gt(20)].groupby("y"):
            picks.append(g.iloc[rng.choice(len(g), min(n, len(g)), replace=False)])
    S = pd.concat(picks)
    print("выборка", len(S), S.groupby("chain").size().to_dict(), flush=True)
    node = {}
    e = S[S.chain == "ethereum"].hash.tolist()
    node.update(eth(e))
    for ch, f in (("bitcoin", btc), ("tron", tron), ("ripple", xrp)):
        for h in S[S.chain == ch].hash:
            node[h] = f(h)
    S["t_node"] = S.hash.map(node)
    S["d_s"] = S.tb - S.t_node
    S[["chain", "y", "hash", "tb", "t_node", "d_s", "tw_t"]].to_csv(f"{C.OUT}/rpc_check.csv", index=False)
    print(S.groupby("chain").d_s.describe().round(1).to_string())
    print("найдено узлом:", S.t_node.notna().mean().round(3))


if __name__ == "__main__":
    main()
