"""s193 — потоковая обработка лент aggTrades: скачал zip → признаки (`tape.features`) → zip удалён.

Задания — `jobs.pkl` (`jobs.py`). Итоги — части `parts/part_NNNN.pkl.gz` (докачка: уже посчитанные задания
пропускаются). User-Agent «research-script/1.0»; при сбое сети — пауза 5 / 20 / 60 с; 404 — файла нет.
Запуск: python3 run.py [число процессов] [предел заданий] [фильтр по тегу]."""
import gzip
import os
import pickle
import sys
import time
import traceback
import urllib.error
import urllib.request
import zlib
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tape  # noqa: E402

D = "/home/user/mc_data/s193"
TMP = f"{D}/tmp"
PARTS = f"{D}/parts"
UA = {"User-Agent": "research-script/1.0"}


def base(perp):
    import re
    return re.sub(r"^(1000000|100000|10000|1000|100|1M)(?=[A-Z0-9])", "", perp)


def url(mkt, s, d):
    day = pd.Timestamp(d, unit="s").strftime("%Y-%m-%d")
    sym = (s if mkt == "um" else base(s)) + "USDT"
    root = "futures/um" if mkt == "um" else "spot"
    return f"https://data.binance.vision/data/{root}/daily/aggTrades/{sym}/{sym}-aggTrades-{day}.zip"


def fetch(u, path):
    for a, pause in enumerate((5, 20, 60, None)):
        try:
            req = urllib.request.Request(u, headers=UA)
            with urllib.request.urlopen(req, timeout=180) as r, open(path, "wb") as f:
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
            return 200
        except urllib.error.HTTPError as e:
            if e.code in (403, 404):
                return e.code
            err = e.code
        except Exception as e:  # noqa: BLE001
            err = str(e)[:80]
        if pause is None:
            return f"err {err}"
        time.sleep(pause)
    return "err"


def work(job):
    mkt, s, d, inj = job["mkt"], job["s"], int(job["d"]), int(job["inj"])
    key = (mkt, s, d)
    path = f"{TMP}/{os.getpid()}_{mkt}_{s}_{d}.zip"
    t0 = time.time()
    code = fetch(url(mkt, s, d), path)
    t1 = time.time()
    if code != 200:
        return dict(key=key, ok=0, code=code)
    try:
        seed = zlib.crc32(f"{mkt}{s}{d}".encode())
        r = tape.features(path, mkt, s, d, inj=inj, seed=seed)
        r["key"] = key
        r["t_dl"] = t1 - t0
        r["t_cpu"] = time.time() - t1
        r["mb"] = os.path.getsize(path) / 1e6
        return r
    except Exception:  # noqa: BLE001
        return dict(key=key, ok=0, code="exc " + traceback.format_exc()[-300:])
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def done_keys():
    out = set()
    for f in sorted(os.listdir(PARTS)):
        if f.endswith(".pkl.gz"):
            with gzip.open(f"{PARTS}/{f}", "rb") as g:
                for r in pickle.load(g):
                    out.add(r["key"])
    return out


def main():
    nproc = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    tag = sys.argv[3] if len(sys.argv) > 3 else ""
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(PARTS, exist_ok=True)
    for f in os.listdir(TMP):
        os.remove(f"{TMP}/{f}")
    J = pd.read_pickle(os.environ.get("S193_JOBS", f"{D}/jobs.pkl"))
    if tag:
        J = J[J.tags.str.contains(tag)]
    have = done_keys()
    J = J[[(m, s, int(d)) not in have for m, s, d in zip(J.mkt, J.s, J.d)]]
    # перемешать, чтобы части шли по всем периодам равномерно
    J = J.sample(frac=1.0, random_state=193)
    if lim:
        J = J.head(lim)
    jobs = J.to_dict("records")
    print(f"к обработке {len(jobs)} заданий (уже есть {len(have)})", flush=True)
    k = len([f for f in os.listdir(PARTS) if f.endswith(".pkl.gz")])
    buf, n, t0, mb, bad = [], 0, time.time(), 0.0, 0
    with Pool(nproc) as pool:
        for r in pool.imap_unordered(work, jobs, chunksize=1):
            buf.append(r)
            n += 1
            mb += r.get("mb", 0.0)
            bad += int(not r.get("ok"))
            if len(buf) >= 300:
                with gzip.open(f"{PARTS}/part_{k:04d}.pkl.gz", "wb", compresslevel=3) as g:
                    pickle.dump(buf, g, protocol=5)
                k += 1
                buf = []
            if n % 100 == 0:
                el = time.time() - t0
                print(f"{n}/{len(jobs)} {el / 60:.1f} мин, {mb / 1024:.2f} ГБ скачано, без файла/ошибка {bad}, "
                      f"осталось ~{el / n * (len(jobs) - n) / 60:.0f} мин", flush=True)
    if buf:
        with gzip.open(f"{PARTS}/part_{k:04d}.pkl.gz", "wb", compresslevel=3) as g:
            pickle.dump(buf, g, protocol=5)
    print(f"готово: {n} заданий, {mb / 1024:.2f} ГБ, {(time.time() - t0) / 60:.1f} мин", flush=True)


if __name__ == "__main__":
    main()
