"""s278 — часовые свечи спота Binance (пары к USDT) за 10.2022–09.2024 из архива data.binance.vision у перпов s117/k_oos
(пара — монета перпа без множителя, иначе сам перп: PEPEUSDT, 1000SATSUSDT). Только данные: время, открытие,
закрытие, оборот $. Не больше ~3 запросов в секунду. Результат — /dev/shm/s278/raw/binance_spot/P0/<перп>.npz.
Запуск: python3 -I fetch_bspot_p0.py"""
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "s259", "study"))
from common259 import base  # noqa: E402

UA = {"User-Agent": "research-script/1.0"}
OUTD = "/dev/shm/s278/raw/binance_spot/P0"
LIST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/spot/monthly/klines/{p}/1h/"
FILE = "https://data.binance.vision/data/spot/monthly/klines/{p}/1h/{p}-1h-{m}.zip"
MONTHS = {f"{y}-{m:02d}" for y in (2022, 2023, 2024) for m in range(1, 13) if "2022-10" <= f"{y}-{m:02d}" <= "2024-09"}


def http(url):
    for k in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429:
                time.sleep(20 + 10 * k)
                continue
        except Exception:
            pass
        time.sleep(2 + 3 * k)
    return b"ERR"


def months_of(pair):
    x = http(LIST.format(p=pair))
    time.sleep(0.35)
    if x in (None, b"ERR"):
        return x
    ms = re.findall(rf"{pair}-1h-(\d{{4}}-\d{{2}})\.zip<", x.decode())
    return sorted(set(ms) & MONTHS)


def main():
    os.makedirs(OUTD, exist_ok=True)
    perps = json.load(open("/dev/shm/s278/perps_oos.json"))["perps"]
    done = 0
    for p in perps:
        f = f"{OUTD}/{p}.npz"
        if os.path.exists(f):
            continue
        rows, pair, failed = [], None, False
        for cand in dict.fromkeys([base(p) + "USDT", p + "USDT"]):
            ms = months_of(cand)
            if ms == b"ERR":
                failed = True                                  # сбой сети — не кэшируем, повтор при новом запуске
                break
            if ms:
                pair = cand
                for m in ms:
                    z = http(FILE.format(p=cand, m=m))
                    time.sleep(0.35)
                    if z in (None, b"ERR"):
                        continue
                    txt = zipfile.ZipFile(io.BytesIO(z)).read(f"{cand}-1h-{m}.csv").decode()
                    for ln in txt.splitlines():
                        q = ln.split(",")
                        if q and q[0].isdigit():
                            t = int(q[0])
                            t = t // 1000 if t < 10 ** 14 else t // 1000000
                            rows.append((t, float(q[1]), float(q[4]), float(q[7])))
                break
        if failed:
            continue
        if rows:
            a = np.array(sorted(set(rows)))
            np.savez_compressed(f + ".tmp.npz", t=a[:, 0].astype(np.int64), o=a[:, 1].astype(np.float32),
                                c=a[:, 2].astype(np.float32), qv=a[:, 3].astype(np.float32), pair=pair)
            os.replace(f + ".tmp.npz", f)
        else:
            np.savez_compressed(f + ".tmp.npz", t=np.zeros(0, np.int64), o=np.zeros(0, np.float32),
                                c=np.zeros(0, np.float32), qv=np.zeros(0, np.float32), pair="")
            os.replace(f + ".tmp.npz", f)
        done += 1
        if done % 20 == 0:
            print(f"{done}/{len(perps)}", flush=True)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
