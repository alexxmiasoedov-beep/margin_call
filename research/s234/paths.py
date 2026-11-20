"""s234 — ход цены после входа по сделкам виртуальных журналов: 5-мин свечи фьючерса Binance (цена сделок) от входа до
входа + срок журнала + 1 ч. Источник — www.binance.com/fapi/v1/klines (из облака fapi.binance.com отвечает 451).
Итог — s234/paths.pkl: {(журнал, вход, монета): массив [время открытия свечи, high, low, close]}.
Запуск из /home/user/mc_data: python3 <repo>/research/s234/paths.py s234/trades_1711.pkl"""
import json
import os
import pickle
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

HOLD = {"📓": 48, "📗": 48, "📘": 48, "📕": 48, "📙": 48, "📘ᶜ": 48, "🇰🇷": 48, "🇰🇷ᶠ": 48, "🇰🇷⭐": 48, "🇹🇷": 48,
        "🟧": 48, "🟦": 48, "🟩": 48, "🏦": 170, "🏦³": 170, "🌊": 3}
UA = {"User-Agent": "research-script/1.0"}
OUT = "s234/paths.pkl"


def kl(sym, t0, t1):
    rows, s = [], int(t0) * 1000
    while s < t1 * 1000:
        url = (f"https://www.binance.com/fapi/v1/klines?symbol={sym}USDT&interval=5m&startTime={s}"
               f"&endTime={int(t1) * 1000}&limit=1500")
        for k in range(4):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
                    j = json.loads(r.read()); break
            except Exception:
                time.sleep(2 * (k + 1)); j = None
        if not j:
            return None
        rows += [[x[0] / 1000, float(x[2]), float(x[3]), float(x[4])] for x in j]
        if len(j) < 1500:
            break
        s = j[-1][0] + 300000
        time.sleep(0.2)
    return np.array(rows) if rows else None


def main(path):
    D = pd.read_pickle(path)
    P = pickle.load(open(OUT, "rb")) if os.path.exists(OUT) else {}
    need = [(r.j, r.t, r.s) for r in D.itertuples() if (r.j, r.t, r.s) not in P]
    print(f"сделок {len(D)}, качаю {len(need)}", flush=True)

    def get(key):
        j, t, s = key
        t0 = int(t // 300 * 300) - 600
        return key, kl(s, t0, t + HOLD.get(j, 48) * 3600 + 3600)
    with ThreadPoolExecutor(4) as ex:
        for i, (key, a) in enumerate(ex.map(get, need)):
            if a is not None:
                P[key] = a
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(need)}", flush=True)
                pickle.dump(P, open(OUT, "wb"))
    pickle.dump(P, open(OUT, "wb"))
    print(f"готово: путей {len(P)}, без данных {len(need) - sum(1 for k in need if k in P)}")


if __name__ == "__main__":
    main(sys.argv[1])
