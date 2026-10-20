import json, pickle, datetime
from concurrent.futures import ThreadPoolExecutor
import bv
syms = json.load(open("kaia/all_usdt.json"))
DAYS = [f"2026-10-{d:02d}" for d in range(1, 20)]
def load(sym):
    try:
        return sym[:-4], bv.kfull(sym[:-4], "klines", "15m", ("2026-09",), DAYS)
    except Exception as e:
        return sym[:-4], None
with ThreadPoolExecutor(24) as ex:
    K = {s: k for s, k in ex.map(load, syms) if k is not None and len(k) > 0}
live = {s: k for s, k in K.items() if k[-1, 0] >= datetime.datetime(2026, 10, 18, 23, tzinfo=datetime.timezone.utc).timestamp()}
print("с данными", len(K), "| торгуются до конца 18.10", len(live))
pickle.dump(live, open("kaia/k15_all.pkl", "wb"))
