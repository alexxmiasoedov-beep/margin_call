"""Данные о позициях для бурных суток: метрики (OI, LSR, тейкеры) по нужным дням, премия 15 мин, фандинг."""
import pickle, datetime
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import bv
need = pickle.load(open("kaia/metrics_need.pkl", "rb")); syms = sorted({s for s, _ in need})
def met(sd):
    try: return sd, bv.metrics(sd[0], [sd[1]])
    except Exception: return sd, None
with ThreadPoolExecutor(24) as ex:
    M = dict(ex.map(met, need))
MET = {}
for (s, d), a in M.items():
    if a is not None and len(a): MET.setdefault(s, []).append(a)
MET = {s: (lambda x: x[np.argsort(x[:, 0])])(np.vstack(v)) for s, v in MET.items()}
print("метрики:", len(MET), "монет", flush=True)
MONTHS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]; DAYS = [f"2026-10-{d:02d}" for d in range(1, 19)]
def prem(s):
    try: return s, bv.klines(s, "premiumIndexKlines", "15m", MONTHS, DAYS)
    except Exception: return s, None
with ThreadPoolExecutor(24) as ex:
    PREM = {s: a for s, a in ex.map(prem, syms) if a is not None}
print("премия:", len(PREM), "монет", flush=True)
def fund(s):
    rows = []
    for m in MONTHS:
        for p in bv.rows(bv.fetch(f"monthly/fundingRate/{s}USDT/{s}USDT-fundingRate-{m}.zip")):
            try: rows.append((int(p[0]) // 1000, int(float(p[1])), float(p[2])))
            except (ValueError, IndexError): pass
    return s, np.array(sorted(rows)) if rows else None
with ThreadPoolExecutor(16) as ex:
    FUND = {s: a for s, a in ex.map(fund, syms) if a is not None}
print("фандинг:", len(FUND), "монет", flush=True)
pickle.dump(dict(MET=MET, PREM=PREM, FUND=FUND), open("kaia/positions.pkl", "wb"))
print("готово", flush=True)
