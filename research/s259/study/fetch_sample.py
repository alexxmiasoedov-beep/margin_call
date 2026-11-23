"""s259 — случайная выборка монето-суток перпов без спота ВНЕ окон событий (для частоты каскадов по OI, вопрос 4):
SAMPLE суток из монето-суток без спота (10.2024–10.2026), не попавших в s259/met_days.json, у перпов без готовых метрик s228.
Тот же разбор, что fetch_metrics.py; итог — s259/met_rand/<перп>.npz (t1, v1, t5, oiv5) и s259/met_rand_days.json.
Запуск: cd /home/user/mc_data && nohup python3 -I <repo>/research/s259/study/fetch_sample.py > s259/fetch_sample.log &"""
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common259 import DAY, OUT, T0, T1  # noqa: E402
from fetch_metrics import get_day  # noqa: E402

SAMPLE = int(os.environ.get("SAMPLE", "2400"))
DIR = "s259/met_rand"


def pick():
    path = f"{OUT}/met_rand_days.json"
    if os.path.exists(path):
        return json.load(open(path))
    U = json.load(open(f"{OUT}/universe.json"))
    ev = json.load(open(f"{OUT}/met_days.json"))
    have = set(f[:-4] for f in os.listdir("s228/met"))
    pool = []
    for s, u in U.items():
        if s in have:
            continue
        a0, a1 = int(max(u["live0"], T0)) + DAY, int(min(u["live1"], T1, u["spot0"] or T1))
        evs = set(ev.get(s, []))
        for d in range((a0 // DAY + 1) * DAY, a1 - DAY, DAY):
            ds = pd.Timestamp(d, unit="s").strftime("%Y-%m-%d")
            if ds not in evs:
                pool.append((s, ds))
    rng = np.random.default_rng(259)
    idx = rng.choice(len(pool), size=min(SAMPLE, len(pool)), replace=False)
    out = {}
    for i in sorted(idx):
        s, ds = pool[i]
        out.setdefault(s, []).append(ds)
    json.dump({"pool": len(pool), "days": out}, open(path, "w"))
    return json.load(open(path))


def main():
    R = pick()
    days = R["days"]
    print(f"монето-суток без спота вне окон событий: {R['pool']}, выборка {sum(len(v) for v in days.values())} у {len(days)} перпов",
          flush=True)
    os.makedirs(DIR, exist_ok=True)
    done = 0; t0 = time.time()
    with ThreadPoolExecutor(4) as ex:
        for p in sorted(days):
            if os.path.exists(f"{DIR}/{p}.npz"):
                continue
            res = list(ex.map(lambda d: (d, get_day(p, d)), days[p]))
            rows = [x for d, r in res if r for x in r]
            A = np.array(rows) if rows else np.zeros((0, 7))
            if len(A):
                A = A[np.argsort(A[:, 0])]
            h = A[(A[:, 0] % 3600) == 0] if len(A) else A
            np.savez_compressed(f"{DIR}/{p}.npz", t1=h[:, 0].astype(np.int64), v1=h[:, 1:].astype(np.float32),
                                t5=A[:, 0].astype(np.int64), oiv5=A[:, 2].astype(np.float32),
                                bad=np.array([d for d, r in res if r is None]))
            done += len(days[p])
            print(f"{time.strftime('%H:%M:%S')} {p}: суток {len(days[p])}, строк {len(A)}; всего {done}, "
                  f"{done / max(time.time() - t0, 1):.1f} сут/с", flush=True)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
