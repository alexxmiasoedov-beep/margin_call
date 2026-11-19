"""s193 — эталон «известная продажа частями»: TWAP-ордера CoW Protocol (сбор s168: work/cow_twap_ours.json) по токенам
с перпом Binance и точные моменты исполнения частей в сети (события Trade контракта GPv2Settlement по владельцу ордера).

Отбор (записан до загрузки лент Binance): шаг части 60–7200 с, частей ≥ 4, длительность ≤ 72 ч, вся заявка ≥ 20 тыс. $
по цене закрытия перпа в день создания; по крупности — до 150 ордеров. Публичные узлы без ключа, паузы при сбоях.
Итог — /home/user/mc_data/s193/cow_fills.pkl: ордер, токен, перп, часть ($), исполнения (блок, время, продано токенов)."""
import json
import os
import sys
import time
import urllib.request

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/margin_call/research/s181/study")
import common181 as C181  # noqa: E402
import treasury_outflows as T181  # noqa: E402

D = "/home/user/mc_data"
OUT = f"{D}/s193"
RPC = ["https://ethereum-rpc.publicnode.com", "https://rpc.mevblocker.io", "https://gateway.tenderly.co/public/mainnet"]
UA = {"User-Agent": "research-script/1.0", "Content-Type": "application/json"}
SETTLE = "0x9008d19f58aabd9ed0d60971565aa8510560ab41"
TRADE = "0xa07a543ab8a018198e99ca0184c93fe9050a79400a0a723441f84de1d972cc17"


def rpc(method, params, tries=6):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for k in range(tries):
        try:
            req = urllib.request.Request(RPC[k % len(RPC)], data=body, headers=UA)
            r = json.load(urllib.request.urlopen(req, timeout=60))
            if "result" in r:
                return r["result"]
        except Exception:  # noqa: BLE001
            pass
        time.sleep(3 + 4 * k)
    return None


def candidates():
    S = json.load(open(f"{D}/s160/sets.json"))
    TOK = S["toks"]
    META = json.load(open(f"{D}/s160/tok_meta.json"))
    L = json.load(open(f"{D}/s168/work/cow_twap_ours.json"))
    X = pd.DataFrame(L, columns=["block", "sell", "buy", "part", "n", "sec", "owner", "tx"])
    X["sell"] = X.sell.str.lower()
    X["owner"] = X.owner.str.lower()
    X = X[X.sell.isin(TOK.keys())].drop_duplicates(["owner", "sell", "part", "n", "sec"]).copy()
    X["dec"] = [int((META.get(s) or {}).get("decimals") or 18) for s in X.sell]
    X["part_tok"] = [p / 10 ** d for p, d in zip(X.part, X.dec)]
    X["t"] = T181.block_time()(X.block.values)
    X["perp"] = X.sell.map(lambda t: TOK[t]["perp"])
    X["hours"] = X.n * X.sec / 3600
    # цена: закрытие перпа в день создания (дневные панели s183), за 1 токен
    px = {}
    for per in ("2022–2024", "2024–2026"):
        P = pd.read_pickle(f"{D}/s183/daily_{per}.pkl")[["s", "d", "c", "qv"]]
        for s, d, c, qv in zip(P.s, P.d, P.c, P.qv):
            px[(s, int(d))] = (c, qv)
    import re
    rows = []
    for r in X.itertuples():
        p = r.perp[:-4] if r.perp.endswith("USDT") else r.perp
        m = re.match(r"^(1000000|1000|1M)(?=[A-Z0-9])", p)
        mult = (1e6 if m.group(1) == "1M" else float(m.group(1))) if m else 1.0
        d = int(r.t // 86400 * 86400)
        v = px.get((p, d)) or px.get((p, d - 86400))
        if v is None:
            continue
        rows.append(dict(r._asdict(), sym=p, price=v[0] / mult, perp_qv=v[1]))
    Y = pd.DataFrame(rows)
    Y["part_usd"] = Y.part_tok * Y.price
    Y["tot_usd"] = Y.part_usd * Y.n
    Y["sh_vol"] = Y.tot_usd / (Y.perp_qv * np.maximum(Y.hours, 1) / 24)
    sel = Y[(Y.sec >= 60) & (Y.sec <= 7200) & (Y.n >= 4) & (Y.hours <= 72) & (Y.tot_usd >= 2e4)]
    sel = sel.sort_values("tot_usd", ascending=False).head(150)
    return Y, sel


def fills(row):
    b0 = int(row.block)
    b1 = b0 + int(row.n * row.sec / 12) + 900
    q = {"fromBlock": hex(b0), "toBlock": hex(b1), "address": SETTLE,
         "topics": [TRADE, "0x" + "0" * 24 + row.owner[2:]]}
    res = rpc("eth_getLogs", [q])
    if res is None:
        return None
    out = []
    for x in res:
        d = bytes.fromhex(x["data"][2:])
        sell = "0x" + d[12:32].hex()
        if sell != row.sell:
            continue
        amt = int.from_bytes(d[64:96], "big") / 10 ** int(row.dec)
        out.append((int(x["blockNumber"], 16), amt, x["transactionHash"]))
    return out


def block_ts(blocks):
    """Точное время блоков пакетными запросами (по 50 в одном HTTP-вызове), с повтором на другом узле."""
    out = {}
    bl = sorted(set(blocks))
    for i in range(0, len(bl), 50):
        chunk = bl[i:i + 50]
        body = json.dumps([{"jsonrpc": "2.0", "id": b, "method": "eth_getBlockByNumber", "params": [hex(b), False]}
                           for b in chunk]).encode()
        for k in range(6):
            try:
                req = urllib.request.Request(RPC[k % 2], data=body, headers=UA)
                r = json.load(urllib.request.urlopen(req, timeout=60))
                for x in r:
                    if x.get("result"):
                        out[int(x["id"])] = int(x["result"]["timestamp"], 16)
                if all(b in out for b in chunk):
                    break
            except Exception:  # noqa: BLE001
                pass
            time.sleep(3 + 4 * k)
        time.sleep(0.3)
    return out


def main():
    Y, sel = candidates()
    print(f"TWAP-продаж токенов с перпом и ценой: {len(Y)}; отобрано {len(sel)} "
          f"(шаг 60–7200 с, частей ≥ 4, ≤ 72 ч, ≥ 20 тыс. $)")
    print(sel[["sym", "n", "sec", "hours", "part_usd", "tot_usd", "sh_vol"]].describe().round(2).to_string())
    res = []
    for k, r in enumerate(sel.itertuples()):
        f = fills(r)
        time.sleep(0.5)
        if not f:
            continue
        ts = block_ts([b for b, _, _ in f])
        res.append(dict(r._asdict(), fills=[(b, ts.get(b), a) for b, a, _ in f]))
        if k % 10 == 0:
            print(k, r.sym, r.n, r.sec, f"{r.tot_usd:,.0f} $", "исполнений", len(f), flush=True)
            pd.to_pickle(res, f"{OUT}/cow_fills.partial.pkl")
    pd.to_pickle(res, f"{OUT}/cow_fills.pkl")
    nf = [len(x["fills"]) for x in res]
    print(f"ордеров с исполнениями: {len(res)}, исполнений всего {sum(nf)}, медиана на ордер {np.median(nf):.0f}")


if __name__ == "__main__":
    main()
