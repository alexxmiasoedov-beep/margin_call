"""s183 — открытый интерес и позиции счетов из архива data.binance.vision (futures/um/daily/metrics, с 12.2021 у альтов)
на последнюю 5-мин отметку воскресенья (≈ понедельник 00:00 UTC) для перпов с оборотом ≥ 2 млн $ в сутки за 7 сут.
Для роста OI берётся и воскресенье неделей раньше. Кэш s22/metrics_full (часовые отметки) используется, если есть.

Запуск: python3 -I oi_fetch.py <период>   Итог: /home/user/mc_data/s183/oi_<период>.pkl
{(перп, сутки): [OI монет, OI $, топ по счетам, топ по позициям, все счета, taker buy/sell]}.
Сеть: 12 потоков, пауза и повтор при сбое; 404 — нет файла (кэшируется как пусто)."""
import io
import os
import pickle
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common183 as C  # noqa: E402

UA = {"User-Agent": "research-script/1.0"}
START = C.ts("2021-12-01")


def day_str(t):
    return pd.Timestamp(int(t), unit="s", tz="UTC").strftime("%Y-%m-%d")


def from_cache(sym, d):
    p = f"{C.D}/s22/metrics_full/{sym}/{day_str(d)}.npy"
    if os.path.exists(p):
        a = np.load(p)
        if len(a):
            return list(map(float, a[-1, 1:7]))
    return None


def fetch(sym, d):
    url = f"https://data.binance.vision/data/futures/um/daily/metrics/{sym}USDT/{sym}USDT-metrics-{day_str(d)}.zip"
    for k in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                z = zipfile.ZipFile(io.BytesIO(r.read()))
            lines = z.read(z.namelist()[0]).decode().splitlines()
            last = None
            for ln in lines[1:]:
                p = ln.split(",")
                if len(p) >= 8:
                    last = p
            if last is None:
                return []
            return [float(x.strip('"')) if x.strip('"') else np.nan for x in last[2:8]]
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return []
            time.sleep(5 * (k + 1))
        except Exception:
            time.sleep(5 * (k + 1))
    return None                                        # сбой сети — не кэшируем


def main(per):
    X = pd.read_pickle(f"{C.OUT}/feat_{per}.pkl")
    X = X[(X.qv7 >= 2e6) & (X.d0 >= START)]
    need = set()
    for s, g in X.groupby("s"):
        ds = set(int(d) - C.DAY for d in g.d0)
        ds |= set(d - 7 * C.DAY for d in ds)
        for d in ds:
            need.add((s, d))
    path = f"{C.OUT}/oi_{per}.pkl"
    res = pickle.load(open(path, "rb")) if os.path.exists(path) else {}
    todo = sorted(k for k in need if k not in res)
    print(per, "нужно", len(need), "уже есть", len(need) - len(todo), flush=True)
    t0 = time.time()

    def job(k):
        s, d = k
        v = from_cache(s, d)
        if v is None:
            v = fetch(s, d)
        return k, v
    done = 0
    with ThreadPoolExecutor(12) as ex:
        for k, v in ex.map(job, todo):
            if v is not None:
                res[k] = v
            done += 1
            if done % 5000 == 0:
                pickle.dump(res, open(path + ".tmp", "wb")); os.replace(path + ".tmp", path)
                print(f"  {done}/{len(todo)} за {(time.time() - t0) / 60:.1f} мин", flush=True)
    pickle.dump(res, open(path + ".tmp", "wb")); os.replace(path + ".tmp", path)
    ok = sum(1 for v in res.values() if v)
    print(per, "готово: записей", len(res), "с данными", ok, f"за {(time.time() - t0) / 60:.1f} мин", flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
