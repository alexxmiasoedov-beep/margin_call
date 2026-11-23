"""s259 — метрики data.binance.vision (OI, лонг/шорт топ-счетов, топ-позиций, всех счетов, taker) за сутки вокруг пампов
и обвалов перпов без спота (s259/met_days.json: сутки события −1…+2), кроме перпов с готовыми часовыми метриками s228.
Итог — /home/user/mc_data/s259/met/<перп>.npz: t1 (часы), v1 (float32: OI, OI $, топ-счета, топ-позиции, все счета, taker —
как s228), t5 и oiv5 (OI $ каждые 5 мин). Не чаще 4 запросов в секунду; сбой сети — пауза и повтор, неотданные сутки —
s259/met_miss.json (докачка при следующем запуске).
Запуск: cd /home/user/mc_data && nohup python3 -I <repo>/research/s259/study/fetch_metrics.py > s259/fetch_metrics.log &"""
import datetime
import io
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np

UTC = datetime.timezone.utc
OUT = "s259/met"
UA = {"User-Agent": "research-script/1.0"}
RATE = 4.0                     # запросов в секунду, на все потоки
_lock = threading.Lock()
_next = [0.0]


def throttle():
    with _lock:
        now = time.time()
        wait = _next[0] - now
        _next[0] = max(now, _next[0]) + 1.0 / RATE
    if wait > 0:
        time.sleep(wait)


def get_day(sym, day):
    """Строки суток: list[[t, OI, OI $, топ-счета, топ-позиции, все счета, taker]]; [] — нет файла (404); None — сбой."""
    s = urllib.parse.quote(f"{sym}USDT")
    url = f"https://data.binance.vision/data/futures/um/daily/metrics/{s}/{s}-metrics-{day}.zip"
    for k in range(4):
        throttle()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            rows = []
            for ln in z.read(z.namelist()[0]).decode().splitlines()[1:]:
                p = [x.strip('"') for x in ln.split(",")]
                if len(p) < 8:
                    continue
                try:
                    t = datetime.datetime.strptime(p[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
                except ValueError:
                    continue
                rows.append([t] + [float(x) if x else np.nan for x in p[2:8]])
            return rows
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            time.sleep(3 * (k + 1))
        except Exception:  # noqa: BLE001
            time.sleep(3 * (k + 1))
    return None


def main():
    days = json.load(open("s259/met_days.json"))
    have = set(f[:-4] for f in os.listdir("s228/met"))
    miss_path = "s259/met_miss.json"
    miss = json.load(open(miss_path)) if os.path.exists(miss_path) else {}
    os.makedirs(OUT, exist_ok=True)
    todo = [p for p in sorted(days) if p not in have and (not os.path.exists(f"{OUT}/{p}.npz") or p in miss)]
    n_all = sum(len(days[p]) for p in todo)
    print(f"перпов {len(todo)}, суток {n_all}", flush=True)
    t0 = time.time(); done = 0
    with ThreadPoolExecutor(4) as ex:
        for p in todo:
            want = miss.get(p, days[p]) if os.path.exists(f"{OUT}/{p}.npz") else days[p]
            res = list(ex.map(lambda d: (d, get_day(p, d)), want))
            bad = [d for d, r in res if r is None]
            rows = [x for d, r in res if r for x in r]
            if os.path.exists(f"{OUT}/{p}.npz"):
                z = np.load(f"{OUT}/{p}.npz")
                old5 = np.c_[z["t5"], z["oiv5"]]
                old1 = np.c_[z["t1"], z["v1"]]
            else:
                old5 = np.zeros((0, 2)); old1 = np.zeros((0, 7))
            A = np.array(rows) if rows else np.zeros((0, 7))
            if len(A):
                A = A[np.argsort(A[:, 0])]
                A = A[np.r_[True, np.diff(A[:, 0]) > 0]]
            h = A[(A[:, 0] % 3600) == 0] if len(A) else A
            v1 = np.r_[old1, h] if len(old1) else h
            v5 = np.r_[old5, A[:, [0, 2]]] if len(old5) else (A[:, [0, 2]] if len(A) else np.zeros((0, 2)))
            v1 = v1[np.argsort(v1[:, 0])] if len(v1) else v1
            v5 = v5[np.argsort(v5[:, 0])] if len(v5) else v5
            np.savez_compressed(f"{OUT}/{p}.npz", t1=v1[:, 0].astype(np.int64), v1=v1[:, 1:].astype(np.float32),
                                t5=v5[:, 0].astype(np.int64), oiv5=v5[:, 1].astype(np.float32))
            if bad:
                miss[p] = bad
            else:
                miss.pop(p, None)
            json.dump(miss, open(miss_path, "w"))
            done += len(want)
            el = time.time() - t0
            print(f"{time.strftime('%H:%M:%S')} {p}: суток {len(want)}, строк {len(A)}, сбоев {len(bad)}; всего {done}/{n_all}, "
                  f"{done / max(el, 1):.1f} сут/с", flush=True)
    print("готово; перпов со сбоями:", len(miss), flush=True)


if __name__ == "__main__":
    main()
