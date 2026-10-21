"""Метрики фьючерса Binance (OI, LSR топ-трейдеров и всех счетов, тейкеры) вокруг каждого пампа: архив daily/metrics за день
пампа и два дня до него. Отметка create_time t описывает t+5 мин (проверено в research/mm) — берём строки с t ≤ T − 5 мин."""
import pickle, datetime, sys
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
import bv
P = pd.read_pickle("s2/pump_TRY.pkl")
day = lambda t: datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%d")
jobs = sorted({(s, day(t - k * 86400)) for s, t in zip(P.s, P.t) for k in (0, 1, 2)})
print("файлов", len(jobs), flush=True)
def get(x):
    s, d = x
    try: return x, bv.metrics(s, [d])
    except Exception: return x, None
M = {}
with ThreadPoolExecutor(16) as ex:
    for i, (x, a) in enumerate(ex.map(get, jobs)):
        if a is not None: M[x] = a
        if i % 2000 == 0: print(i, len(M), flush=True)
rows = []
for s, T in zip(P.s, P.t):
    parts = [M[(s, day(T - k * 86400))] for k in (2, 1, 0) if (s, day(T - k * 86400)) in M]
    r = dict(s=s, t=T)
    if parts:
        a = np.concatenate(parts); a = a[np.argsort(a[:, 0])]; a = a[a[:, 0] <= T - 300]
        # колонки: t, OI, OI $, LSR топ по счетам, LSR топ по позициям, LSR все счета, тейкеры buy/sell
        if len(a) >= 12:
            def at(dt):
                k = np.searchsorted(a[:, 0], T - 300 - dt, "right") - 1
                return a[k] if k >= 0 and a[k, 0] >= T - 300 - dt - 900 else None
            now = a[-1]
            if now[0] >= T - 1200:
                r.update(oi_usd=now[2], top_acc=now[3], top_pos=now[4], all_acc=now[5])
                for nm, dt in (("1h", 3600), ("4h", 14400), ("24h", 86400)):
                    p = at(dt)
                    if p is not None:
                        r[f"oi_ch{nm}"] = now[1] / p[1] - 1 if p[1] > 0 else np.nan
                        r[f"top_acc_ch{nm}"] = now[3] - p[3]; r[f"top_pos_ch{nm}"] = now[4] - p[4]; r[f"all_acc_ch{nm}"] = now[5] - p[5]
                tk = a[a[:, 0] > T - 300 - 3600]; r["taker_1h"] = np.nanmean(tk[:, 6]) if len(tk) else np.nan
    rows.append(r)
D = pd.DataFrame(rows); D.to_pickle("s6/ev_metrics.pkl")
print(D.notna().mean().round(2).to_dict())
