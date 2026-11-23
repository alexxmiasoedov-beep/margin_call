"""s252 — пилот: переводы токенов BNB Chain (перпы без спота Binance) на адреса бирж через SQD Portal, один запрос за раз
(study/sqdq.py), продолжение после обрыва.
Токены — s252/bsc_tokens.json (BEP-20 с историей CMC); получатели — метки EVM `bot/cex_labels.tsv` действующих бирж
(KEEP, без кастоди; у многих бирж адреса общие для EVM-сетей — проверено в sweep_find), адреса сметания Binance в BNB Chain
(s249/collectors.json) и найденные в sweep_find.json; запрос портала не больше ~250 КБ — до 3 фильтров по 1000 адресов. Фильтр SQD: address = токены, topic0 = Transfer,
topic2 = получатели (кусками по 1000 в нескольких фильтрах одного запроса).
Итог — s252/raw/<кусок>.jsonl: [блок, время, токен, от, кому, сумма в единицах токена, tx].
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/collect_cex.py <ГГГГ-ММ-ДД начало> <ГГГГ-ММ-ДД конец> [кусков]"""
import json
import os
import sys
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sqdq  # noqa: E402

T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
LABELS = "/home/user/mc_main/bot/cex_labels.tsv"      # только чтение


def pad(a):
    return "0x" + "0" * 24 + a[2:]


KEEP = {"MEXC", "Bitget", "Gate.io", "Bybit", "OKX", "KuCoin", "HTX", "BingX", "CoinEx", "LBank", "BitMart", "XT.com",
        "Coinbase", "Kraken", "Crypto.com", "Upbit", "Bitvavo", "Bitfinex", "Binance", "Bitstamp", "CoinW", "CoinDCX",
        "Bitkub", "WhiteBIT", "BtcTurk", "Paribu", "Phemex", "Woo", "AscendEX", "DigiFinex", "Coinstore", "BigONE",
        "Biconomy", "BitVenus", "Bitrue", "ProBit", "Indodax", "Tokocrypto", "Bullish", "Robinhood", "Gemini", "Bitpanda",
        "WazirX", "Coinone", "Korbit", "GOPAX", "BTSE", "Deepcoin", "Flipster", "OX.FUN", "blockscout-exchange"}
DROP_NAME = ("Prime", "Custody")                         # кастоди и прайм-брокеры — не продажа на бирже


def receivers():
    """{адрес: биржа}: метки EVM нужных бирж (без кастоди), адреса сметания Binance в BNB Chain и найденные sweep_find."""
    rec = {}
    for line in open(LABELS, encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        p = line.rstrip("\n").split("\t")
        a, ex, name = p[0].strip().lower(), p[1].strip(), (p[2] if len(p) > 2 else "")
        if a.startswith("0x") and len(a) == 42 and ex in KEEP and not any(w in name for w in DROP_NAME):
            rec.setdefault(a, ex)
    for a in json.load(open("s249/collectors.json")):
        rec[a.lower()] = "Binance"
    if os.path.exists("s252/extra_receivers.json"):           # адреса сметания без меток (sweep_usdt.py, sweep_find.py)
        for a, ex in json.load(open("s252/extra_receivers.json")).items():
            rec.setdefault(a.lower(), ex)
    if os.path.exists("s252/sweep_find.json"):
        for day, v in json.load(open("s252/sweep_find.json")).items():
            for ex, top in v.items():
                if ex in ("blocks", "n_dep"):
                    continue
                for a, n, ns, nt in top:
                    if ns >= 3:                                  # сходятся переводы ≥ 3 адресов пополнения
                        rec.setdefault(a.lower(), ex)
    return rec


def main():
    a, b = sys.argv[1], sys.argv[2]
    W = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    TB = json.load(open("s252/bsc_tokens.json"))
    TK = json.load(open("s252/tokens.json"))
    dec = {v["contract"]: v["decimals"] for s, v in TB.items() if v.get("cmc") and v.get("decimals") is not None
           and TK[s].get("alpha_chain") == "bsc" and TK[s]["bsc_native"]}           # токен Alpha в BNB Chain, свой адрес
    recm = receivers()
    json.dump(recm, open("s252/receivers.json", "w"), indent=0)
    rec = sorted(recm)
    lo = sqdq.block_guess(pd.Timestamp(a, tz="UTC").timestamp())
    hi = sqdq.block_guess(pd.Timestamp(b, tz="UTC").timestamp())
    flts = [{"address": sorted(dec), "topic0": [T], "topic2": [pad(x) for x in rec[k:k + 1000]]}
            for k in range(0, len(rec), 1000)]
    fields = {"block": {"number": True, "timestamp": True},
              "log": {"address": True, "topics": True, "data": True, "transactionHash": True}}
    os.makedirs("s252/raw", exist_ok=True)
    step = (hi - lo) // W + 1
    print(f"блоки {lo}–{hi}, кусков {W}, токенов {len(dec)}, получателей {len(rec)}", flush=True)
    for k in range(W):
        c0, c1 = lo + k * step, min(hi, lo + (k + 1) * step - 1)
        prog = f"s252/raw/prog_{k}.json"
        cur = json.load(open(prog))["next"] if os.path.exists(prog) else c0
        if cur > c1:
            continue
        f = open(f"s252/raw/part_{k}.jsonl", "a")
        n, t1 = 0, time.time()
        while cur <= c1:
            q = {"type": "evm", "fromBlock": cur, "toBlock": c1, "fields": fields, "logs": flts}
            bl = sqdq.stream(q)
            if not bl:
                break
            for blk in bl:
                h = blk["header"]
                for lg in blk.get("logs") or []:
                    tok = lg["address"].lower()
                    amt = int(lg["data"], 16) / 10 ** dec.get(tok, 18) if lg["data"] not in ("0x", "") else 0.0
                    f.write(json.dumps([h["number"], h["timestamp"], tok, "0x" + lg["topics"][1][-40:],
                                        "0x" + lg["topics"][2][-40:], amt, lg.get("transactionHash")]) + "\n")
                    n += 1
            f.flush()
            cur = bl[-1]["header"]["number"] + 1
            json.dump({"next": cur}, open(prog, "w"))
        print(f"[{k}] {c0}–{c1}: переводов {n}, {time.time() - t1:.0f} с, запросов {sqdq.STAT}", flush=True)


if __name__ == "__main__":
    main()
