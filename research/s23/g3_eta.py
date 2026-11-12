"""Г3 — самовозбуждение активности. Для каждой монеты и среза T (00:00 UTC): 15-мин число сделок за 3 суток до T,
делённое на суточный профиль монеты (медиана по времени суток за 30 суток до T), — относительная активность x;
INAR(8) МНК: x_t = μ + Σ α_k x_(t−k); коэффициент ветвления η = Σ α_k (оценка Кирхнера для процесса Хоукса на бинах).
Также η за 30 суток (норма монеты). Кэш s23/eta.pkl: DataFrame срез × монета (ETA3, ETA30). Запуск из папки с данными."""
import os
import pickle
import sys
import numpy as np, pandas as pd
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from common23 import CRYPTO, K, SY

P_LAG, WIN, BASE = 8, 3 * 96, 30 * 96


def inar(x, p=P_LAG):
    n = len(x)
    if n <= 4 * p or not np.isfinite(x).all() or x.std() == 0:
        return np.nan
    Z = np.column_stack([np.ones(n - p)] + [x[p - k:n - k] for k in range(1, p + 1)])
    a = np.linalg.lstsq(Z, x[p:], rcond=None)[0]
    return float(a[1:].sum())


def run():
    rows3, rows30 = {}, {}
    for j, (s, c) in enumerate(zip(SY, CRYPTO)):
        if not c:
            continue
        a = K[s]; t = a["t"].astype(np.int64); nn = a["n"].astype(np.float64); live = a["qv"] > 0
        nn[~live] = np.nan
        T0 = t[0] // 86400 * 86400 + 31 * 86400
        e3, e30 = {}, {}
        for T in range(int(T0), int(t[-1]), 86400):
            i = int(np.searchsorted(t, T))                      # свечи до T: t < T
            if i < BASE:
                continue
            base = nn[i - BASE:i].reshape(30, 96)
            if np.isnan(base).mean() > 0.1:
                continue
            prof = np.nanmedian(base, axis=0)
            if not np.all(prof > 0):
                continue
            x = (base / prof).ravel()
            w = x[-WIN:]
            if np.isnan(w).any():
                continue
            e3[T] = inar(w)
            xb = x[~np.isnan(x)] if np.isnan(x).any() else x
            e30[T] = inar(x) if not np.isnan(x).any() else np.nan
        rows3[s], rows30[s] = pd.Series(e3, dtype=float), pd.Series(e30, dtype=float)
        if j % 100 == 0:
            print(f"  {j}/{len(SY)}", flush=True)
    out = dict(ETA3=pd.DataFrame(rows3), ETA30=pd.DataFrame(rows30))
    pickle.dump(out, open("s23/eta.pkl", "wb"), protocol=4)
    return out


if __name__ == "__main__":
    E = run()
    print({k: v.shape for k, v in E.items()})
    d = E["ETA3"].stack()
    print("η за 3 сут: квантили 5/25/50/75/95%:", np.round(np.nanpercentile(d, [5, 25, 50, 75, 95]), 3))
    d = E["ETA30"].stack()
    print("η за 30 сут: квантили:", np.round(np.nanpercentile(d, [5, 25, 50, 75, 95]), 3))
