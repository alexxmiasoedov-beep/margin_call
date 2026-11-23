"""s249 — сбор переводов токенов BNB Chain на адреса сметания Binance через SQD Portal (без ключа), несколькими потоками
по кускам блоков, с продолжением после обрыва. Токены и десятичные знаки — s249/bsc_circ.json и s249/decimals.json,
адреса сметания — s249/collectors.json (список). Итог — s249/raw/part_<k>.jsonl: [блок, время, токен, от, кому, сумма, tx].
Запуск из /home/user/mc_data: python3 <repo>/research/s249/collect.py <ГГГГ-ММ-ДД начало> <ГГГГ-ММ-ДД конец> [потоков]
Дособрать куски из файла плана только по части токенов (noeth — монеты без сети ETH у Binance, eth — с сетью ETH):
python3 <repo>/research/s249/collect.py plan <файл плана> <noeth|eth> <префикс частей>"""
import json
import os
import sys
import threading
import time

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sqd  # noqa: E402

T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def pad(a):
    return "0x" + "0" * 24 + a[2:]


def worker(k, lo, hi, q0, dec, out_dir, lock):
    prog = os.path.join(out_dir, f"prog_{k}.json")
    cur = json.load(open(prog))["next"] if os.path.exists(prog) else lo
    f = open(os.path.join(out_dir, f"part_{k}.jsonl"), "a")
    n = 0
    while cur <= hi:
        q = dict(q0, fromBlock=cur, toBlock=hi)
        try:
            bl = sqd.stream(q, tries=60)
        except Exception as e:
            with lock:
                print(f"[{k}] сбой {e!r} на блоке {cur}, пауза 60 с", flush=True)
            time.sleep(60)
            continue
        if not bl:
            break
        for b in bl:
            h = b["header"]
            for l in b.get("logs") or []:
                tok = l["address"].lower()
                amt = int(l["data"], 16) / 10 ** dec.get(tok, 18) if l["data"] not in ("0x", "") else 0.0
                f.write(json.dumps([h["number"], h["timestamp"], tok, "0x" + l["topics"][1][-40:], "0x" + l["topics"][2][-40:],
                                    amt, l.get("transactionHash")]) + "\n")
                n += 1
        f.flush()
        cur = bl[-1]["header"]["number"] + 1
        json.dump({"next": cur}, open(prog, "w"))
    with lock:
        print(f"[{k}] готово: {lo}–{hi}, переводов {n}", flush=True)


def rest(plan_f, subset, pfx):
    """Куски из плана — только токены части subset; части и продолжение — s249/raw/part_<pfx><j>.jsonl, prog_<pfx><j>.json."""
    C = json.load(open("s249/bsc_circ.json"))
    D = json.load(open("s249/decimals.json"))
    want = {C[fs]["contract"] for fs in C if bool(C[fs]["eth"]) == (subset == "eth")}
    dec = {C[fs]["contract"]: d for fs, d in D.items() if d >= 0 and C[fs]["contract"] in want}
    cols = json.load(open("s249/collectors.json"))
    q0 = {"type": "evm", "fields": {"block": {"number": True, "timestamp": True},
                                     "log": {"address": True, "topics": True, "data": True, "transactionHash": True}},
          "logs": [{"address": sorted(dec), "topic0": [T], "topic2": [pad(x) for x in cols]}]}
    plan = [tuple(x) for x in json.load(open(plan_f))]
    lock = threading.Lock()
    th = [threading.Thread(target=worker, args=(f"{pfx}{j}", a, b, q0, dec, "s249/raw", lock)) for j, (a, b) in enumerate(plan)]
    print(f"дособор {subset}: кусков {len(plan)}, блоков {sum(b - a + 1 for a, b in plan)}, токенов {len(dec)}", flush=True)
    for t in th:
        t.start()
    for t in th:
        t.join()


def main():
    if sys.argv[1] == "plan":
        return rest(sys.argv[2], sys.argv[3], sys.argv[4])
    a, b = sys.argv[1], sys.argv[2]
    W = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    C = json.load(open("s249/bsc_circ.json"))
    D = json.load(open("s249/decimals.json"))
    dec = {C[fs]["contract"]: d for fs, d in D.items() if d >= 0}
    cols = json.load(open("s249/collectors.json"))
    lo = sqd.block_guess(pd.Timestamp(a, tz="UTC").timestamp())
    hi = sqd.block_guess(pd.Timestamp(b, tz="UTC").timestamp())
    q0 = {"type": "evm", "fields": {"block": {"number": True, "timestamp": True},
                                     "log": {"address": True, "topics": True, "data": True, "transactionHash": True}},
          "logs": [{"address": sorted(dec), "topic0": [T], "topic2": [pad(x) for x in cols]}]}
    out_dir = "s249/raw"
    os.makedirs(out_dir, exist_ok=True)
    lock = threading.Lock()
    plan_f = os.path.join(out_dir, "plan.json")              # продолжение: куски, оставшиеся от прошлого запуска
    if os.path.exists(plan_f):
        plan = [tuple(x) for x in json.load(open(plan_f))]
        th = [threading.Thread(target=worker, args=(f"p{j}", a, b, q0, dec, out_dir, lock)) for j, (a, b) in enumerate(plan)]
    else:
        step = (hi - lo) // W + 1
        th = [threading.Thread(target=worker, args=(k, lo + k * step, min(hi, lo + (k + 1) * step - 1), q0, dec, out_dir, lock))
              for k in range(W)]
    print(f"блоки {lo}–{hi}, потоков {W}, токенов {len(dec)}, адресов сметания {len(cols)}", flush=True)
    for t in th:
        t.start()
    for t in th:
        t.join()


if __name__ == "__main__":
    main()
