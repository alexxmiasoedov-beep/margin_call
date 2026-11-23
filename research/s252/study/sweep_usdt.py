"""s252 — адреса сметания бирж в BNB Chain «сейчас» по USDT (публичный узел bsc-rpc.publicnode.com, логи последних ~2 сут,
фильтр — адрес контракта USDT BEP-20 и topic1 = адреса пополнения биржи из Ethereum, s195_deposits.pkl, 120 сут до
05.11.2026; у клиента биржи один адрес на все EVM-сети). USDT — самый частый токен пополнений, поэтому за сутки видно,
куда биржа сметает. Итог — /home/user/mc_data/s252/sweep_usdt.json: {биржа: [[получатель, переводов, отправителей], …]}.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/sweep_usdt.py"""
import collections
import json
import time
import urllib.request

import pandas as pd

U = "https://bsc-rpc.publicnode.com"
HDR = {"Content-Type": "application/json", "User-Agent": "research-script/1.0"}
T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
USDT = "0x55d398326f99059ff775485246999027b3197955"
EXCH = ["Bitget", "OKX", "HTX", "Bybit", "MEXC", "Gate.io", "KuCoin", "BingX", "Coinbase", "Kraken", "Crypto.com", "Binance"]


def rpc(m, p):
    for i in range(4):
        try:
            r = urllib.request.urlopen(urllib.request.Request(U, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m,
                                                                                  "params": p}).encode(), headers=HDR), timeout=90)
            d = json.loads(r.read())
            if "error" in d:
                raise RuntimeError(d["error"])
            return d["result"]
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(3 + 3 * i)
    raise RuntimeError(str(err))


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def main():
    D = pd.read_pickle("s195_deposits.pkl")
    tmax = D.t.max()
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
        for a in range(h - 180000, h, 15000):
            for k in range(0, len(addrs), 100):
                try:
                    L = rpc("eth_getLogs", [{"fromBlock": hex(a), "toBlock": hex(min(h, a + 14999)), "address": USDT,
                                             "topics": [T, [pad(x) for x in addrs[k:k + 100]]]}])
                except RuntimeError:
                    n_err += 1
                    continue
                for lg in L:
                    to = "0x" + lg["topics"][2][-40:]
                    cnt[to] += 1
                    snd[to].add(lg["topics"][1])
        out[ex] = {"n_dep": len(addrs), "errors": n_err, "top": [[a, n, len(snd[a])] for a, n in cnt.most_common(6)]}
        print(ex, "адресов", len(addrs), "сбоев", n_err, out[ex]["top"][:4], flush=True)
    json.dump({"blocks": [h - 180000, h], "res": out}, open("s252/sweep_usdt.json", "w"), indent=1)


if __name__ == "__main__":
    main()
