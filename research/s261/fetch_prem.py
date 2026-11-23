"""s261 — премия к индексу (premiumIndexKlines 15 мин, закрытие свечи) для периода Б (19.10–19.11.2026): s12/prem.pkl
кончается 18.10.2026. Только перпы без спота Binance, живые в Б (вселенная s260/nospot). Дневные архивы
data.binance.vision, не больше 4 запросов в секунду. Итог — s261/prem_b.pkl: {перп: (время открытия, премия)}.
Запуск из /home/user/mc_data: python3 -I <repo>/research/s261/fetch_prem.py"""
import io
import os
import pickle
import sys
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s260"))
import nospot as N  # noqa: E402

UA = {"User-Agent": "research-script/1.0"}
DAYS = pd.date_range("2026-10-18", "2026-11-19", freq="D").strftime("%Y-%m-%d").tolist()
_lock = threading.Lock()
_last = [0.0]


def get(url):
    for k in range(4):
        with _lock:                                            # не чаще 4 запросов в секунду
            w = _last[0] + 0.25 - time.time()
            if w > 0:
                time.sleep(w)
            _last[0] = time.time()
        try:
            u = urllib.parse.quote(url, safe=":/")              # перпы с иероглифами в названии (龙虾 и т. п.)
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            print(f"  {url.rsplit('/', 1)[-1]}: HTTP {e.code}, попытка {k + 1}", flush=True)
            time.sleep(5 * (k + 1))
        except Exception as e:
            print(f"  {url.rsplit('/', 1)[-1]}: {type(e).__name__} {e}, попытка {k + 1}", flush=True)
            time.sleep(5 * (k + 1))
    return None


def one(s):
    cache = f"s261/pb/{s}.npz"                                 # готовые монеты — из кэша (повторный запуск)
    if os.path.exists(cache):
        z = np.load(cache)
        return s, ((z["t"], z["p"]) if len(z["t"]) else None)
    rows = []
    for d in DAYS:
        b = get(f"https://data.binance.vision/data/futures/um/daily/premiumIndexKlines/{s}USDT/15m/{s}USDT-15m-{d}.zip")
        if not b:
            continue
        z = zipfile.ZipFile(io.BytesIO(b))
        for ln in z.read(z.namelist()[0]).decode().splitlines():
            p = ln.split(",")
            if p and p[0].isdigit():
                rows.append((int(p[0]) // 1000, float(p[4])))
    os.makedirs("s261/pb", exist_ok=True)
    if not rows:
        np.savez(cache, t=np.zeros(0, np.int64), p=np.zeros(0, np.float32))
        return s, None
    a = np.array(sorted(set(rows)))
    v = (a[:, 0].astype(np.int64), a[:, 1].astype(np.float32))
    np.savez(cache, t=v[0], p=v[1])
    return s, v


def main():
    U = N.universe()
    S = [s for s, u in U.items() if u["live1"] >= N.TA - N.DAY and (not u["spot0"] or u["spot0"] > N.TA)]
    print(f"перпов без спота, живых в Б: {len(S)}; дней {len(DAYS)}", flush=True)
    out = {}
    with ThreadPoolExecutor(4) as ex:
        for k, (s, v) in enumerate(ex.map(one, S)):
            if v is not None:
                out[s] = v
            if k % 20 == 0:
                print(time.strftime("%H:%M:%S"), k, len(out), flush=True)
    os.makedirs("s261", exist_ok=True)
    pickle.dump(out, open("s261/prem_b.pkl", "wb"))
    print("готово:", len(out), "перпов", sum(len(v[0]) for v in out.values()), "свечей", flush=True)


if __name__ == "__main__":
    main()
