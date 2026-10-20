import json, pickle, datetime
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import bv
syms = sorted(pickle.load(open("kaia/k15_all.pkl", "rb")).keys())
MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
DAYS = [f"2026-10-{d:02d}" for d in range(1, 19)]
def load(s):
    try:
        return s, bv.kfull(s, "klines", "15m", MONTHS, DAYS)
    except Exception:
        return s, None
with ThreadPoolExecutor(24) as ex:
    K = {s: k for s, k in ex.map(load, syms) if k is not None and len(k) > 96 * 8}
pickle.dump(K, open("kaia/k15_6m.pkl", "wb"))
print("монет", len(K), "| свечей всего", sum(len(k) for k in K.values()))
