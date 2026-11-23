"""s252 — адреса сметания бирж в сети Base «сейчас» (шлюз Tenderly без ключа, eth_getLogs по 1000 блоков, как s243).
Адреса пополнения биржи — из Ethereum (s195_deposits.pkl, 120 сут до 05.11.2026, до 200 на биржу); переводы USDC и токенов
перпов без спота с главной сетью Base от этих адресов (topic1) за последние ~0,5 сут. Получатель, на который сходятся
переводы нескольких адресов пополнения, — адрес сметания. Итог — /home/user/mc_data/s252/sweep_base.json.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/sweep_base.py"""
import collections
import json
import time
import urllib.request

import pandas as pd

URL = "https://base.gateway.tenderly.co"
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
EXCH = ["Bitget", "Bybit", "MEXC", "Gate.io", "KuCoin", "OKX", "HTX", "Coinbase", "Binance"]


def rpc(m, p):
    err = None
    for k in range(5):
        try:
            req = urllib.request.Request(URL, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
                                         headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                j = json.loads(r.read())
            if "result" in j:
                return j["result"]
            err = str(j.get("error"))[:200]
        except Exception as e:  # noqa: BLE001
            err = str(e)[:200]
        time.sleep(2 * 2 ** k)
    raise RuntimeError(err)


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def main():
    D = pd.read_pickle("s195_deposits.pkl")
    tmax = D.t.max()
    TK = json.load(open("s252/tokens.json"))
    toks = [USDC] + sorted({c["platforms"]["base"] for r in TK.values() for c in r["cg"]
                            if r.get("alpha_chain") == "base" and c["platforms"].get("base")})[:9]
    h = int(rpc("eth_blockNumber", []), 16)
    out = {}
    for ex in EXCH:
        d = D[D.exch == ex]
        w = d[d.t >= tmax - 120 * 86400]
        if w.frm.nunique() < 30:
            w = d.sort_values("t").tail(4000)
        addrs = w.drop_duplicates("frm", keep="last").frm.tolist()[-200:]
        cnt, snd = collections.Counter(), collections.defaultdict(set)
        n_err = 0
        for a in range(h - 20000, h, 1000):
            try:
                L = rpc("eth_getLogs", [{"fromBlock": hex(a), "toBlock": hex(a + 999), "address": toks,
                                         "topics": [T, [pad(x) for x in addrs]]}])
            except RuntimeError:
                n_err += 1
                continue
            for lg in L:
                to = "0x" + lg["topics"][2][-40:]
                cnt[to] += 1
                snd[to].add(lg["topics"][1])
        out[ex] = {"n_dep": len(addrs), "errors": n_err, "top": [[a, n, len(snd[a])] for a, n in cnt.most_common(5)]}
        print(ex, "адресов", len(addrs), "сбоев", n_err, out[ex]["top"][:3], flush=True)
    json.dump({"blocks": [h - 20000, h], "tokens": toks, "res": out}, open("s252/sweep_base.json", "w"), indent=1)


if __name__ == "__main__":
    main()
