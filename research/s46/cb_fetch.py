"""s46 — часовые свечи Coinbase (публичный API, без ключа) для монет с фьючерсом Binance, 01.10.2024–20.10.2026.
Список пар — s44/cb_products.json (монета → пары к USD/USDC/USDT). Ответ API — [время, low, high, open, close, объём],
не больше 300 свечей за запрос. Итог — s46/cb1h.pkl: {монета: DataFrame(T — конец часа, usd — оборот в $, c — закрытие)}.
Запуск из папки с данными: python3 <repo>/research/s46/cb_fetch.py"""
import datetime as dt
import json
import os
import pickle
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

T0 = dt.datetime(2024, 10, 1, tzinfo=dt.timezone.utc)
T1 = dt.datetime(2026, 10, 20, tzinfo=dt.timezone.utc)
STEP = dt.timedelta(hours=300)


def get(url):
    for k in range(6):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                                     timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return []
            time.sleep(2 + 3 * k)
        except Exception:
            time.sleep(2 + 3 * k)
    return None


def product(pid):
    rows, t = [], T0
    while t < T1:
        e = min(t + STEP, T1)
        x = get(f"https://api.exchange.coinbase.com/products/{pid}/candles?granularity=3600"
                f"&start={t:%Y-%m-%dT%H:%M:%SZ}&end={e:%Y-%m-%dT%H:%M:%SZ}")
        if x:
            rows += x
        t = e
        time.sleep(0.25)
    if not rows:
        return pid, None
    a = np.array(rows, dtype=float)
    d = pd.DataFrame({"T": a[:, 0].astype(np.int64) + 3600, "usd": a[:, 5] * a[:, 4], "c": a[:, 4]})
    return pid, d.drop_duplicates("T").sort_values("T").reset_index(drop=True)


def main():
    os.makedirs("s46", exist_ok=True)
    bases = json.load(open("s44/cb_products.json"))
    pids = [p for v in bases.values() for p in v]
    out = {}
    t0 = time.time()
    with ThreadPoolExecutor(3) as ex:
        for n, (pid, d) in enumerate(ex.map(product, pids)):
            if d is not None and len(d):
                out[pid] = d
            if n % 25 == 24:
                print(f"  пар {n + 1}/{len(pids)}, {time.time() - t0:.0f} с", flush=True)
    by = {}
    for b, ps in bases.items():
        ds = [out[p] for p in ps if p in out]
        if not ds:
            continue
        d = pd.concat(ds).groupby("T").agg(usd=("usd", "sum"), c=("c", "last")).reset_index()
        by[b] = d
    pickle.dump(by, open("s46/cb1h.pkl", "wb"))
    print(f"готово: монет {len(by)}, пар со свечами {len(out)} из {len(pids)}", flush=True)


if __name__ == "__main__":
    main()
