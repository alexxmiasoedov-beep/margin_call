"""Прогнозная ставка фандинга минута за минутой на 48 ч после входа (как её видит бот через premiumIndex) → predpath.pkl."""
import datetime, pickle, numpy as np
from concurrent.futures import ThreadPoolExecutor
import bv
from sim import SIG, FUND
UTC = datetime.timezone.utc
day = lambda t: datetime.datetime.fromtimestamp(t, UTC).strftime("%Y-%m-%d")
def job(s):
    te = s["te"]; F = FUND.get(s["sym"])
    if F is None or len(F) < 2: return None
    A = bv.kfull(s["sym"], "premiumIndexKlines", "1m", (), sorted({day(t) for t in range(te - 9 * 3600, te + 50 * 3600, 3600)}))
    if A is None: return None
    tm, pr = A[:, 0].astype(int), A[:, 4]
    out_t, out_r = [], []
    for t in range(te, te + 48 * 3600, 300):                  # каждые 5 минут, как часто бот смотрит
        k = np.searchsorted(F[:, 0], t, "right") - 1
        if k < 1: continue
        start = F[k, 0]; ih = (F[k, 0] - F[k - 1, 0]) / 3600 if k + 1 >= len(F) else (F[k + 1, 0] - F[k, 0]) / 3600
        m = (tm >= start) & (tm < t)
        if m.sum() < 1: continue
        p = np.average(pr[m], weights=np.arange(1, m.sum() + 1))
        out_t.append(t); out_r.append((p + np.clip(0.0001 - p, -0.0005, 0.0005)) * 100 / 8)   # % в час
    return (s["sym"], s["ep"]), (np.array(out_t), np.array(out_r))
with ThreadPoolExecutor(12) as ex:
    R = dict(x for x in ex.map(job, SIG) if x)
pickle.dump(R, open("predpath.pkl", "wb")); print("готово", len(R))
