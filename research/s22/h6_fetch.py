"""Г6: 5-мин метрики OI (data.binance.vision, кэш s20/metrics) по 50 самым торгуемым перпам за весь период свечей —
для суммарного OI рынка и поиска каскадов ликвидаций. Запуск из папки с данными: python3 .../s22/h6_fetch.py"""
import datetime
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common22 import DAY, K, NONCRYPTO, UTC, live, metrics_day

if __name__ == "__main__":
    vol = {s: float(a["qv"].sum()) for s, a in K.items() if s not in NONCRYPTO}
    top = sorted(vol, key=vol.get, reverse=True)[:50]
    open("s22/top50.txt", "w").write("\n".join(top))
    need = []
    for s in top:
        lo, hi = live(s)
        for d in np.arange(lo // DAY * DAY, hi + DAY, DAY):
            need.append((s, datetime.datetime.fromtimestamp(d, UTC).strftime("%Y-%m-%d")))
    print("топ-50:", " ".join(top), f"\nдней метрик {len(need)}", flush=True)
    t0 = time.time(); done = [0]

    def get(x):
        a = metrics_day(*x); done[0] += 1
        if done[0] % 4000 == 0:
            print(f"  {done[0]}/{len(need)} за {(time.time() - t0) / 60:.0f} мин", flush=True)
        return len(a)
    with ThreadPoolExecutor(24) as ex:
        n = list(ex.map(get, need))
    print(f"готово: с данными {sum(1 for x in n if x)}, пустых {sum(1 for x in n if not x)}, {(time.time() - t0) / 60:.0f} мин")
