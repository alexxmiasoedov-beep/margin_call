"""Часовые свечи рынков к воне на Upbit и Bithumb (у монет с фьючерсом Binance) и курс USDT/KRW,
01.10.2024 – 18.10.2026 — для доли Кореи в обороте и корейской премии на всей истории, а не только вокруг пампов.
Результат — s15/kr_candles_<биржа>.pkl: {монета: {"t": начало часа, с; "c": закрытие, KRW; "v": оборот, KRW}}.

Запуск из папки с данными: python3 s15/kr_candles.py [upbit|bithumb]"""
import datetime
import os
import pickle
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kr_listings import API, get, iso, utc

UTC = datetime.timezone.utc
T0, T1 = datetime.datetime(2024, 10, 1, tzinfo=UTC), datetime.datetime(2026, 10, 18, tzinfo=UTC)
K = pickle.load(open("s2/k2y.pkl", "rb"))
THREADS = {"upbit": 4, "bithumb": 6}                           # лимит свечей Upbit — 10 запросов в секунду с IP, у Bithumb выше


def candles(ex, market):
    rows, to = {}, T1
    while to > T0:
        c = get(f"{API[ex]}/v1/candles/minutes/60?market={market}&count=200&to={iso(to, ex)}"); time.sleep(0.12)
        if not c:
            break
        for x in c:
            rows[int(utc(x).timestamp())] = (float(x["trade_price"]), float(x["candle_acc_trade_price"]))
        first = min(utc(x) for x in c)
        if len(c) < 200 or first >= to:
            break
        to = first
    if not rows:
        return None
    t = np.array(sorted(rows), dtype=np.int64)
    return {"t": t, "c": np.array([rows[x][0] for x in t], dtype=np.float32), "v": np.array([rows[x][1] for x in t], dtype=np.float32)}


def exchange(ex):
    path = f"s15/kr_candles_{ex}.pkl"
    if os.path.exists(path):
        return
    mk = [m["market"] for m in get(f"{API[ex]}/v1/market/all") or [] if m["market"].startswith("KRW-")]
    keep = [m for m in mk if m == "KRW-USDT" or any(k in K for k in (m[4:], "1000" + m[4:], "1000000" + m[4:]))]
    with ThreadPoolExecutor(THREADS[ex]) as pool:
        res = dict(zip([m[4:] for m in keep], pool.map(lambda m: candles(ex, m), keep)))
    res = {k: v for k, v in res.items() if v is not None}
    pickle.dump(res, open(path, "wb"))
    print(f"{ex}: рынков к воне {len(mk)}, с фьючерсом Binance {len(keep) - 1}, со свечами {len(res)}", flush=True)


if __name__ == "__main__":
    exs = sys.argv[1:] or ["upbit", "bithumb"]
    with ThreadPoolExecutor(len(exs)) as pool:
        list(pool.map(exchange, exs))
