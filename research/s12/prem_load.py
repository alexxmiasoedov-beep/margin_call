"""Премия фьючерса к индексу (basis) по всем фьючерсам: 15-мин свечи premiumIndexKlines из архива Binance
(месячные 2024-10…2026-09 + дневные 2026-10-01…18), кэш bv → s12/prem.pkl: {символ: (время, премия на закрытии свечи)}."""
import pickle, sys, os, datetime
import numpy as np
sys.path.insert(0, os.getcwd())
import bv
from concurrent.futures import ThreadPoolExecutor
K = pickle.load(open("s2/k2y.pkl", "rb"))
MONTHS = [f"2024-{m:02d}" for m in (10, 11, 12)] + [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]
DAYS = [f"2026-10-{d:02d}" for d in range(1, 19)]
def one(s):
    rows = []
    for m in MONTHS:
        if K[s]["t"][-1] < datetime.datetime.strptime(m + "-01", "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc).timestamp() - 86400 * 40:
            continue
        rows += bv.rows(bv.fetch(f"monthly/premiumIndexKlines/{s}USDT/15m/{s}USDT-15m-{m}.zip"))
    for d in DAYS:
        rows += bv.rows(bv.fetch(f"daily/premiumIndexKlines/{s}USDT/15m/{s}USDT-15m-{d}.zip"))
    out = []
    for p in rows:
        try: out.append((int(p[0]) // 1000, float(p[4])))
        except (ValueError, IndexError): pass
    if not out: return s, None
    a = np.array(sorted(set(out)))
    return s, (a[:, 0].astype(np.int64), a[:, 1].astype(np.float32))
PR = {}
with ThreadPoolExecutor(16) as ex:
    for i, (s, v) in enumerate(ex.map(one, list(K))):
        if v is not None: PR[s] = v
        if i % 100 == 0: print(datetime.datetime.now().strftime("%H:%M:%S"), i, len(PR), flush=True)
pickle.dump(PR, open("s12/prem.pkl", "wb"), protocol=4)
print("готово, символов", len(PR), "свечей", sum(len(v[0]) for v in PR.values()), flush=True)
