"""s68 — часовые свечи всех рынков X-EUR Bitvavo (публичный API, без ключа), 01.10.2024–19.10.2026, по 1440 свечей за запрос.
Ответ — [время мс, open, high, low, close, объём], от новых к старым. Итог — s68/bvv1h.pkl: {монета: DataFrame(T — конец
часа, eur — оборот в евро)}. Запуск из папки с данными: python3 <repo>/research/s68/bvv_fetch.py"""
import json
import os
import pickle
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

T0, T1 = 1727740800, 1792368000                               # 01.10.2024 и 19.10.2026, UTC
STEP = 1440 * 3600


def get(url):
    for k in range(6):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research"}), timeout=30).read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return []
            time.sleep(2 + 4 * k)
        except Exception:
            time.sleep(2 + 4 * k)
    return None


def one(market):
    rows = []
    for a in range(T0, T1, STEP):
        b = min(a + STEP, T1)
        x = get(f"https://api.bitvavo.com/v2/{market}/candles?interval=1h&limit=1440&start={a * 1000}&end={b * 1000}")
        if x:
            rows += x
        time.sleep(0.15)
    if not rows:
        return market, None
    a = np.array([[int(r[0]) // 1000, float(r[4]), float(r[5])] for r in rows])
    d = pd.DataFrame({"T": a[:, 0].astype(np.int64) + 3600, "eur": a[:, 1] * a[:, 2]})
    return market, d.drop_duplicates("T").sort_values("T").reset_index(drop=True)


def main():
    os.makedirs("s68", exist_ok=True)
    mk = [m["market"] for m in get("https://api.bitvavo.com/v2/markets") if m["market"].endswith("-EUR")]
    out = {}
    t0 = time.time()
    with ThreadPoolExecutor(6) as ex:
        for n, (m, d) in enumerate(ex.map(one, mk)):
            if d is not None and len(d):
                out[m[:-4]] = d
            if n % 50 == 49:
                print(f"  {n + 1}/{len(mk)}, {time.time() - t0:.0f} с", flush=True)
    pickle.dump(out, open("s68/bvv1h.pkl", "wb"))
    print("готово: рынков со свечами", len(out), "из", len(mk), flush=True)


if __name__ == "__main__":
    main()
