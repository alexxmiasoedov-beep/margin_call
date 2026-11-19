"""s192 — часовые свечи спота Binance (пары к USDT) за 09.2019–09.2020 для монет перпов периода (k_2019.pkl).

Архив data.binance.vision (без ключей). Пара — монета перпа без множителя (как s23/spot_fetch и s118/spot_oos).
Кэш — /home/user/mc_data/s192/spotcache с именами как у s23/spot_fetch (monthly_klines_<SYM>USDT_1h_<SYM>USDT-1h-<ГГГГ-ММ>.zip;
404 — пустой файл), его же читает common183.spot_hourly. Итог — /home/user/mc_data/s192/spot1h_2019.pkl в формате
s23/spot1h.pkl: {перп: массив [время открытия сек, оборот $, агрессивные покупки $, сделки, закрытие]}.
Запуск: python3 <repo>/research/s192/spot_2019.py"""
import io
import os
import pickle
import re
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np

OUT = "/home/user/mc_data/s192"
CACHE = f"{OUT}/spotcache"
BASE = "https://data.binance.vision/data/spot"
MONTHS = ["2019-09", "2019-10", "2019-11", "2019-12"] + [f"2020-{m:02d}" for m in range(1, 10)]
UA = "research-script/1.0"


def get(path):
    fn = os.path.join(CACHE, path.replace("/", "_"))
    if os.path.exists(fn):
        return open(fn, "rb").read() or None
    for i in range(5):
        try:
            req = urllib.request.Request(f"{BASE}/{path}", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            open(fn + ".tmp", "wb").write(data); os.replace(fn + ".tmp", fn)
            return data
        except urllib.error.HTTPError as e:
            if e.code == 404:
                open(fn, "wb").close()
                return None
        except Exception:
            pass
        time.sleep(3 * (i + 1))
    return None                                                   # сбой сети не кэшируется


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


def one(s):
    for b in dict.fromkeys((s, re.sub(r"^(1000000|100000|10000|1000)", "", s))):
        got = []
        for m in MONTHS:
            got += rows(get(f"monthly/klines/{b}USDT/1h/{b}USDT-1h-{m}.zip"))
        if got:
            return s, b, np.array(sorted(set(got)))
    return s, None, None


def main():
    os.makedirs(CACHE, exist_ok=True)
    K = pickle.load(open(f"{OUT}/k_2019.pkl", "rb"))
    syms = sorted(K)
    del K
    S, pairs = {}, {}
    with ThreadPoolExecutor(8) as ex:
        for s, b, a in ex.map(one, syms):
            if a is not None:
                S[s] = a
                pairs[s] = b
    pickle.dump(S, open(f"{OUT}/spot1h_2019.pkl", "wb"), protocol=4)
    no = [s for s in syms if s not in S]
    first = {s: int(a[0, 0]) for s, a in S.items()}
    late = sorted((t, s) for s, t in first.items() if t > 1567296000)
    print(f"перпов {len(syms)}, со спотом Binance к USDT {len(S)}; без спота: {no}", flush=True)
    print("пары спота, открытые позже 01.09.2019:",
          ", ".join(f"{s} {time.strftime('%Y-%m-%d', time.gmtime(t))}" for t, s in late), flush=True)


if __name__ == "__main__":
    main()
