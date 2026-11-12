"""Спотовые часовые свечи Binance (data.binance.vision, без ключей) для криптофьючерсов панели: оборот, агрессивные покупки,
число сделок, закрытие. Месяцы 2024-10…2026-09 и дни 2026-10-01…18. Пара — монета фьючерса без множителя (1000PEPE →
PEPEUSDT). Время в архиве спота с 2025 г. — в микросекундах. Кэш архивов — s23/spotcache/, итог — s23/spot1h.pkl:
{фьючерс: массив [время открытия, оборот $, агрессивные покупки $, сделки, закрытие]}. Запуск из папки с данными."""
import io
import os
import pickle
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
import numpy as np
CSY = pickle.load(open("s22/grid.pkl", "rb"))["syms"]          # все фьючерсы архива; у акций и индексов спота нет (404)

BASE = "https://data.binance.vision/data/spot"
CACHE = "s23/spotcache"; os.makedirs(CACHE, exist_ok=True)
MONTHS = [f"2024-{m:02d}" for m in (10, 11, 12)] + [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]
DAYS = [f"2026-10-{d:02d}" for d in range(1, 19)]


def get(path):
    fn = os.path.join(CACHE, path.replace("/", "_"))
    if os.path.exists(fn):
        return open(fn, "rb").read() or None
    for i in range(4):
        try:
            with urllib.request.urlopen(f"{BASE}/{path}", timeout=60) as r:
                data = r.read()
            open(fn, "wb").write(data)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                open(fn, "wb").close()
                return None
        except Exception:
            pass
        time.sleep(2 + 3 * i)
    return None


def rows(data):
    if not data:
        return []
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return []
    out = []
    for ln in z.read(z.namelist()[0]).decode().splitlines():
        p = ln.split(",")
        if p and p[0][:1].isdigit() and len(p) > 10:
            t = int(p[0]); t = t // 1_000_000 if t > 10 ** 14 else t // 1000
            out.append((t, float(p[7]), float(p[10]), float(p[8]), float(p[4])))
    return out


def pair(s):
    for base in (s, re.sub(r"^(1000000|100000|10000|1000)", "", s)):
        if get(f"monthly/klines/{base}USDT/1h/{base}USDT-1h-2025-06.zip") or get(f"monthly/klines/{base}USDT/1h/{base}USDT-1h-2026-06.zip") \
                or get(f"monthly/klines/{base}USDT/1h/{base}USDT-1h-2025-01.zip"):
            return base
    return None


def one(s):
    b = pair(s)
    if not b:
        return s, None
    out = []
    for m in MONTHS:
        out += rows(get(f"monthly/klines/{b}USDT/1h/{b}USDT-1h-{m}.zip"))
    for d in DAYS:
        out += rows(get(f"daily/klines/{b}USDT/1h/{b}USDT-1h-{d}.zip"))
    if not out:
        return s, None
    a = np.array(sorted(set(out)))
    return s, a


if __name__ == "__main__":
    t0 = time.time(); S = {}
    with ThreadPoolExecutor(16) as ex:
        for i, (s, a) in enumerate(ex.map(one, CSY)):
            if a is not None:
                S[s] = a
            if i % 50 == 0:
                print(f"  {i}/{len(CSY)}: со спотом {len(S)}, {time.time() - t0:.0f} с", flush=True)
    pickle.dump(S, open("s23/spot1h.pkl", "wb"), protocol=4)
    print(f"готово: фьючерсов со спотом {len(S)} из {len(CSY)}, часов {sum(len(a) for a in S.values())}, {time.time() - t0:.0f} с")
