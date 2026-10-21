"""Полные 15-мин свечи всех USDT-M фьючерсов за 01.10.2024–18.10.2026 (из кэша архива) + фандинг из архива → s2/k2y.pkl, s2/fund2y.pkl.
Колонки свечей: t (int64), o, h, l, c, qv (объём $), tb (покупки тейкеров $), n (сделок) — float32."""
import pickle, datetime, sys
import numpy as np
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "mm2")
import bv
from load2y import symbols, MONTHS, DAYS
S = symbols(); print("символов", len(S), flush=True)
def one(s):
    try: k = bv.kfull(s, "klines", "15m", MONTHS, DAYS)
    except Exception: k = None
    if k is None or len(k) < 96 * 3: return s, None, None
    arr = dict(t=k[:, 0].astype(np.int64), o=k[:, 1].astype(np.float32), h=k[:, 2].astype(np.float32), l=k[:, 3].astype(np.float32),
               c=k[:, 4].astype(np.float32), qv=k[:, 6].astype(np.float32), tb=k[:, 8].astype(np.float32), n=k[:, 7].astype(np.float32))
    fr = []
    for m in MONTHS:
        for p in bv.rows(bv.fetch(f"monthly/fundingRate/{s}USDT/{s}USDT-fundingRate-{m}.zip")):
            try: fr.append((int(p[0]) // 1000, float(p[1]), float(p[2])))
            except (ValueError, IndexError): pass
    return s, arr, np.array(sorted(fr)) if fr else None
K, F = {}, {}
with ThreadPoolExecutor(16) as ex:
    for n, (s, a, f) in enumerate(ex.map(one, S)):
        if a is not None: K[s] = a
        if f is not None: F[s] = f
        if n % 100 == 0: print(datetime.datetime.now().strftime("%H:%M:%S"), n, flush=True)
pickle.dump(K, open("s2/k2y.pkl", "wb"), protocol=4); pickle.dump(F, open("s2/fund2y.pkl", "wb"), protocol=4)
print("монет", len(K), "| свечей", sum(len(a["t"]) for a in K.values()), "| с фандингом", len(F), flush=True)
