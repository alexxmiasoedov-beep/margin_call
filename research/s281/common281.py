"""s281 — общее: часовая сетка перпов периода (кэш s278 `/dev/shm/s278/perp_<P>.npz`: закрытие на конце часа, оборот
часа), индекс альтов и сигнал «тот же час прошлых суток». Доходы сделок здесь не считаются."""
import numpy as np

H, DAY = 3600, 86400
PER = {"2020–2022": "P00", "2022–2024": "P0", "2024–2026": "P1"}
T0 = {"P00": "2020-10-01", "P0": "2022-10-01", "P1": "2024-10-01"}
LOOK, NMIN, TMIN, MMIN = 20, 15, 3.0, 0.002


def grid(per):
    import pandas as pd
    z = np.load(f"/dev/shm/s278/perp_{PER[per]}.npz", allow_pickle=True)
    P, C, Q, F = list(z["P"]), z["C"], z["Q"].astype(np.float64), z["F"]
    t0 = int(pd.Timestamp(T0[PER[per]], tz="UTC").timestamp())
    T = t0 + np.arange(C.shape[1]) * H                          # начало часа k
    R = np.full_like(C, np.nan)
    R[:, 1:] = C[:, 1:] / C[:, :-1] - 1                         # доход часа k: закрытие k−1 → закрытие k
    tr = (Q > 0) & np.roll(Q > 0, 1, axis=1)
    tr[:, 0] = False
    R[~tr] = np.nan
    cq = np.concatenate([np.zeros((len(P), 1)), np.cumsum(Q, axis=1)], axis=1)
    k = np.arange(C.shape[1])
    v24 = cq[:, k] - cq[:, np.maximum(k - 24, 0)]               # оборот 24 ч до начала часа k (часы k−24 … k−1)
    age = T[None, :] - F[:, None]
    iB = P.index("BTC")
    okA = (v24 >= 5e6) & np.isfinite(R)
    okA[iB] = False
    alt = np.nanmean(np.where(okA, np.clip(R, -0.5, 0.5), np.nan), axis=0)
    E = R - alt[None, :]                                        # остаток к индексу альтов
    return P, T, R, E, v24, age, alt


def signal(E, shift=0):
    """m, t, n по остаткам того же часа (сдвиг shift ч) прошлых LOOK суток: E[k − 24j + shift], j = 1 … LOOK."""
    n_c, n_h = E.shape
    S = np.full((LOOK, n_c, n_h), np.nan, np.float32)
    for j in range(1, LOOK + 1):
        lag = 24 * j - shift
        if lag <= 0:
            continue
        S[j - 1, :, lag:] = E[:, :-lag]
    n = np.isfinite(S).sum(axis=0)
    m = np.nanmean(S, axis=0)
    sd = np.nanstd(S, axis=0, ddof=1)
    t = m / (sd / np.sqrt(np.maximum(n, 1)))
    return m, t, n
