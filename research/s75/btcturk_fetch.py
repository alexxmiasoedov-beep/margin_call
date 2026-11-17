"""s75 — часовые свечи всех пар к лире BTCTurk (публичный API graph-api.btcturk.com, без ключа), 01.10.2024–19.10.2026,
кусками по 90 сут. Ответ — t (начало часа), o, h, l, c, v (объём в монете). Итог — s75/btcturk1h.pkl: {пара: массив
[начало часа, оборот в лирах (v × c)]}. Запуск из папки с данными: python3 <repo>/research/s75/btcturk_fetch.py"""
import json
import os
import pickle
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

T0, T1 = 1727740800, 1792368000
STEP = 90 * 86400


def get(url):
    for k in range(5):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research"}), timeout=60).read())
        except Exception:
            time.sleep(2 + 3 * k)
    return None


def one(pair):
    rows = {}
    for a in range(T0, T1, STEP):
        b = min(a + STEP, T1)
        j = get(f"https://graph-api.btcturk.com/v1/klines/history?symbol={pair}&resolution=60&from={a}&to={b}")
        if j and j.get("s") == "ok":
            for t, c, v in zip(j["t"], j["c"], j["v"]):
                rows[int(t)] = float(c) * float(v)
        time.sleep(0.2)
    if not rows:
        return pair, None
    ks = sorted(rows)
    return pair, np.array([[k, rows[k]] for k in ks])


def main():
    os.makedirs("s75", exist_ok=True)
    info = get("https://api.btcturk.com/api/v2/server/exchangeinfo")
    pairs = sorted(x["name"] for x in info["data"]["symbols"] if x["denominator"] == "TRY")
    out = {}
    t0 = time.time()
    with ThreadPoolExecutor(4) as ex:
        for n, (p, a) in enumerate(ex.map(one, pairs)):
            if a is not None and len(a):
                out[p] = a
            if n % 40 == 39:
                print(f"  {n + 1}/{len(pairs)}, {time.time() - t0:.0f} с", flush=True)
    pickle.dump(out, open("s75/btcturk1h.pkl", "wb"))
    print("готово: пар со свечами", len(out), "из", len(pairs), flush=True)


if __name__ == "__main__":
    main()
