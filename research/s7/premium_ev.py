"""Премия фьючерса к индексу (спот нескольких бирж) вокруг каждого пампа: архив premiumIndexKlines 15m (месяц пампа и
предыдущий; октябрь 2026 — дневные файлы). Признаки строго до T: премия в свече-триггере, макс. в пампе, средняя за сутки."""
import datetime, pickle
import numpy as np, pandas as pd
from concurrent.futures import ThreadPoolExecutor
import bv
UTC = datetime.timezone.utc
D = pd.read_pickle("s6/feat.pkl")[["s", "t", "dur"]]
def periods(t):
    d = datetime.datetime.fromtimestamp(t, UTC); m0 = d.strftime("%Y-%m"); p = (d.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
    out = []
    for m in (p, m0):
        if m < "2026-10": out.append(("m", m))
    if d >= datetime.datetime(2026, 10, 1, tzinfo=UTC):
        for k in range(0, 3):
            dd = d - datetime.timedelta(days=k)
            if dd >= datetime.datetime(2026, 10, 1, tzinfo=UTC): out.append(("d", dd.strftime("%Y-%m-%d")))
    return out
need = sorted({(s, kind, per) for s, t in zip(D.s, D.t) for kind, per in periods(t)})
print("файлов", len(need), flush=True)
def get(x):
    s, kind, per = x
    try: return x, bv.klines(s, "premiumIndexKlines", "15m", (per,) if kind == "m" else (), (per,) if kind == "d" else ())
    except Exception: return x, None
P = {}
with ThreadPoolExecutor(16) as ex:
    for i, (x, a) in enumerate(ex.map(get, need)):
        if a is not None and len(a): P.setdefault(x[0], []).append(a)
        if i % 2000 == 0: print(i, flush=True)
P = {s: np.unique(np.vstack(v), axis=0) for s, v in P.items()}
rows = []
for s, t, dur in zip(D.s, D.t, D.dur):
    a = P.get(s); r = dict(s=s, t=t)
    if a is not None:
        j = np.searchsorted(a[:, 0], t - 900)
        if j < len(a) and a[j, 0] == t - 900 and j >= 96:
            n = int(dur // 15)
            r.update(pr_trig=a[j, 4], pr_max=a[j - n + 1:j + 1, 2].max(), pr_base=a[j - n, 4], pr_24=a[j - 96:j - n, 4].mean(), pr_min24=a[j - 96:j - n, 3].min())
    rows.append(r)
R = pd.DataFrame(rows); R.to_pickle("s7/ev_premium.pkl"); print(R.notna().mean().round(2).to_dict())
