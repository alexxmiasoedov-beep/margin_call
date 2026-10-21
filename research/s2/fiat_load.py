"""15-мин свечи спотовых пар Binance к фиатным валютам (TRY и др.) за 10.2024–10.2026 для монет с пампами + курсы USDT/фиат → s2/fiat_{Q}.pkl."""
import pickle, re, sys, io, zipfile, datetime
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import bv
Q = sys.argv[1] if len(sys.argv) > 1 else "TRY"
MONTHS = [f"2024-{m:02d}" for m in (10, 11, 12)] + [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]
DAYS = [f"2026-10-{d:02d}" for d in range(1, 19)]
syms = set(open("s2/spot_syms.txt").read().split())
EV = pickle.load(open("mm2/pumps2y.pkl", "rb"))["EV"]
strip = lambda s: re.sub(r"^(1000000|100000|10000|1000)", "", s)
pairs = {}
for s in sorted({e["s"] for e in EV}):
    for name in (s, strip(s)):
        if f"{name}{Q}" in syms: pairs[s] = name; break
print(Q, "монет с пампами, у которых есть пара:", len(pairs), flush=True)
def load(sym):
    out = []
    for m in MONTHS: out += bv.rows(bv.fetch_spot(f"monthly/klines/{sym}/15m/{sym}-15m-{m}.zip"))
    for d in DAYS: out += bv.rows(bv.fetch_spot(f"daily/klines/{sym}/15m/{sym}-15m-{d}.zip"))
    if not out: return sym, None
    a = np.array([[int(p[0]) // (1000000 if len(p[0]) > 13 else 1000), float(p[4]), float(p[7])] for p in out])   # t, close, объём в фиате
    a = a[np.argsort(a[:, 0])]; _, u = np.unique(a[:, 0], return_index=True); return sym, a[u]
with ThreadPoolExecutor(16) as ex:
    D = dict(ex.map(load, [f"{n}{Q}" for n in pairs.values()] + [f"USDT{Q}"]))
D = {k: v for k, v in D.items() if v is not None}
pickle.dump(dict(pairs=pairs, D=D), open(f"s2/fiat_{Q}.pkl", "wb"))
print("загружено пар:", len(D), "| курс USDT:", f"USDT{Q}" in D, flush=True)
