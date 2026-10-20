import pickle
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import bv
need = pickle.load(open("kaia/prem_need.pkl", "rb"))
OCT = [f"2026-10-{d:02d}" for d in range(1, 17)]
def get(sm):
    s, m = sm
    try:
        a = bv.klines(s, "premiumIndexKlines", "15m", () if m == "2026-10" else (m,), OCT if m == "2026-10" else ())
        return sm, a
    except Exception:
        return sm, None
with ThreadPoolExecutor(24) as ex:
    R = dict(ex.map(get, need))
P = {}
for (s, m), a in R.items():
    if a is not None and len(a): P.setdefault(s, []).append(a)
P = {s: (lambda x: x[np.unique(x[:, 0], return_index=True)[1]])(np.vstack(v)) for s, v in P.items()}
pickle.dump(P, open("kaia/prem_sig.pkl", "wb"))
print("премия загружена:", len(P), "монет из", len({s for s, _ in need}), "| пустых пар:", sum(1 for a in R.values() if a is None or not len(a)))
