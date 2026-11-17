"""s102 — 15-мин свечи спотовых пар Binance к лире (XXXTRY) и USDTTRY за 10.2024–10.2026 из архива data.binance.vision для
фьючерсов из s2/k2y.pkl: список пар — exchangeInfo зеркала data-api.binance.vision (все статусы, в том числе снятые).
Кэш помесячно — s15/try/<пара>-<ГГГГ-ММ>.npy ([время открытия, сек; закрытие; объём в лирах]), как в s15/kr_raid_tr.py.
Запуск из папки с данными: python3 <repo>/research/s102/try_fetch.py"""
import io
import json
import os
import re
import sys
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
from common import K  # noqa: E402

MONTHS = [f"2024-{m:02d}" for m in (10, 11, 12)] + [f"2025-{m:02d}" for m in range(1, 13)] + \
         [f"2026-{m:02d}" for m in range(1, 11)]


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 + 3 * k)
        except Exception:
            time.sleep(2 + 3 * k)
    return b"ERR"


def month(pair, ym):
    path = f"s15/try/{pair}-{ym}.npy"
    if os.path.exists(path):
        return
    data = get(f"https://data.binance.vision/data/spot/monthly/klines/{pair}/15m/{pair}-15m-{ym}.zip")
    if data == b"ERR":
        return                                                       # сетевой сбой — не кэшируем, повторный запуск докачает
    arr = np.zeros((0, 3))
    if data:
        z = zipfile.ZipFile(io.BytesIO(data))
        rows = [ln.split(",") for ln in z.read(z.namelist()[0]).decode().splitlines() if ln and ln[0].isdigit()]
        ts = np.array([int(x[0]) for x in rows], dtype=np.int64)
        ts = np.where(ts > 1e14, ts // 1000, ts) // 1000
        arr = np.c_[ts, np.array([float(x[4]) for x in rows]), np.array([float(x[7]) for x in rows])]
    np.save(path, arr)


def main():
    os.makedirs("s15/try", exist_ok=True)
    ei = json.loads(get("https://data-api.binance.vision/api/v3/exchangeInfo?permissions=SPOT"))
    tr = {x["baseAsset"]: x["symbol"] for x in ei["symbols"] if x["quoteAsset"] == "TRY"}
    pairs = {}
    for s in K:
        for name in (s, re.sub(r"^(1000000|100000|10000|1000)", "", s)):
            if name in tr:
                pairs[s] = tr[name]
                break
    json.dump(pairs, open("s102/try_pairs.json", "w"))
    jobs = [(p, m) for p in sorted(set(pairs.values())) + ["USDTTRY"] for m in MONTHS]
    print(f"пар к лире в exchangeInfo: {len(tr)}; с фьючерсом в архиве: {len(pairs)}; файлов: {len(jobs)}", flush=True)
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda j: month(*j), jobs))
    miss = [j for j in jobs if not os.path.exists(f"s15/try/{j[0]}-{j[1]}.npy")]
    print(f"готово; не скачано из-за сбоев: {len(miss)}", flush=True)


if __name__ == "__main__":
    os.makedirs("s102", exist_ok=True)
    main()
