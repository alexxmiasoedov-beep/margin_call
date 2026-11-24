"""s282 — сбор событий «прострел»: минимум (максимум) 15-мин свечи ушёл от закрытия прошлой свечи.

Для каждой свечи i с оборотом (и прошлой свечой с оборотом, без дыры) считаются только величины ДО конца свечи и до неё:
- dl = l[i] / c[i−1] − 1 (уход минимума), dh = h[i] / c[i−1] − 1 (уход максимума) — от закрытия прошлой свечи;
- turn — оборот перпа за прошлые 24 ч (без свечи i), $; age — сутки от первой свечи с оборотом;
- sig — медианный размах 15-мин свечи (h / l − 1) монеты за 7 сут до начала суток свечи (масштаб волатильности);
- r1h — ход за час до свечи: c[i−1] / c[i−5] − 1.
Закрытие свечи i и всё после неё не берутся (запрет записи до расчёта s283).

Событие — dl ≤ −min(3%, 4·sig) или dh ≥ min(3%, 4·sig). Таблица событий — /dev/shm/s282/ev_<период>.pkl,
по свечам рынка (сколько перпов живо, медианы dl и dh, BTC, число перпов с dl ≤ −X) — /dev/shm/s282/bars_<период>.npz,
монето-свечи по группам оборота — /dev/shm/s282/liq_<период>.json.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s282/study/wicks_build.py <период> [<период> …]"""
import json
import pickle
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))
from common282 import BAR, DAY, H, K_LEVELS, PER, TMP, TURN_BINS, X_LEVELS, crypto_perps  # noqa: E402


def mr7(t, rng):
    """Медиана размаха за 7 сут до начала суток (по суткам UTC). Возвращает (сутки, значение); нужно ≥ 3 сут данных."""
    days = np.unique(t // DAY)
    st = np.searchsorted(t, days * DAY - 7 * DAY)
    en = np.searchsorted(t, days * DAY)
    out = np.full(len(days), np.nan)
    for k, (s, e) in enumerate(zip(st, en)):
        x = rng[s:e]
        x = x[np.isfinite(x)]
        if len(x) >= 3 * 96:
            out[k] = np.median(x)
    return days, out


def build(per):
    cfg = PER[per]
    t0, t1 = cfg["t0"], cfg["t1"]
    tic = time.time()
    K = pickle.load(open(cfg["k"], "rb"))
    P = crypto_perps(K)
    grid = np.arange(t0, t1, BAR, dtype=np.int64)
    G = len(grid)
    DL = np.full((len(P), G), np.nan, np.float32)
    DH = np.full((len(P), G), np.nan, np.float32)
    AGE7 = np.zeros((len(P), G), bool)
    liq = np.zeros(len(TURN_BINS) - 1, np.int64)
    liq_half = np.zeros((2, len(TURN_BINS) - 1), np.int64)
    ev = []
    for j, p in enumerate(P):
        a = K[p]
        t = a["t"].astype(np.int64)
        h, l, c, qv = (a[f].astype(np.float64) for f in ("h", "l", "c", "qv"))
        live = qv > 0
        nz = np.flatnonzero(live)
        if len(nz) < 96:
            continue
        first = t[nz[0]]
        i = np.arange(1, len(t))
        ok = live[i] & live[i - 1] & (t[i] - t[i - 1] == BAR) & (t[i] >= t0) & (t[i] < t1) & (c[i - 1] > 0) & (l[i] > 0)
        i = i[ok]
        if not len(i):
            continue
        cp = c[i - 1]
        dl = l[i] / cp - 1
        dh = h[i] / cp - 1
        cs = np.r_[0.0, np.cumsum(qv)]
        lo = np.searchsorted(t, t[i] - DAY)
        turn = cs[i] - cs[lo]
        age = (t[i] - first) / DAY
        rng = np.where(live & (l > 0), h / np.where(l > 0, l, np.nan) - 1, np.nan)
        days, mr = mr7(t, rng)
        sig = mr[np.searchsorted(days, t[i] // DAY)]
        i5 = i - 5
        r1h = np.where((i5 >= 0) & (t[i - 1] - t[np.maximum(i5, 0)] == 4 * BAR) & live[np.maximum(i5, 0)],
                       cp / c[np.maximum(i5, 0)] - 1, np.nan)
        gi = (t[i] - t0) // BAR
        DL[j, gi] = dl
        DH[j, gi] = dh
        AGE7[j, gi] = age >= 7
        a7 = age >= 7
        liq += np.histogram(turn[a7], TURN_BINS)[0]
        mid = cfg["mid"]
        liq_half[0] += np.histogram(turn[a7 & (t[i] < mid)], TURN_BINS)[0]
        liq_half[1] += np.histogram(turn[a7 & (t[i] >= mid)], TURN_BINS)[0]
        thr = np.minimum(0.03, 4 * np.where(np.isfinite(sig), sig, np.inf))
        m = (dl <= -thr) | (dh >= thr)
        if m.any():
            ev.append(pd.DataFrame(dict(s=p, t=t[i][m], dl=dl[m], dh=dh[m], turn=turn[m], age=age[m], sig=sig[m],
                                        r1h=r1h[m])))
    E = pd.concat(ev, ignore_index=True)
    E["s"] = E["s"].astype("category")
    E = E.sort_values(["s", "t"], kind="stable").reset_index(drop=True)
    E.to_pickle(f"{TMP}/ev_{per}.pkl")
    live_n = np.isfinite(DL).sum(0)
    live7 = (np.isfinite(DL) & AGE7).sum(0)
    with np.errstate(all="ignore"):
        med_dl = np.nanmedian(DL, axis=0)
        med_dh = np.nanmedian(DH, axis=0)
    bi = P.index("BTC") if "BTC" in P else None
    btc_dl = DL[bi] if bi is not None else np.full(G, np.nan)
    btc_dh = DH[bi] if bi is not None else np.full(G, np.nan)
    cnt_dn = np.stack([(DL <= -x).sum(0) for x in X_LEVELS])
    cnt_up = np.stack([(DH >= x).sum(0) for x in X_LEVELS])
    cnt_dn7 = np.stack([((DL <= -x) & AGE7).sum(0) for x in X_LEVELS])
    cnt_up7 = np.stack([((DH >= x) & AGE7).sum(0) for x in X_LEVELS])
    np.savez_compressed(f"{TMP}/bars_{per}.npz", grid=grid, live=live_n, live7=live7, med_dl=med_dl, med_dh=med_dh,
                        btc_dl=btc_dl, btc_dh=btc_dh, cnt_dn=cnt_dn, cnt_up=cnt_up, cnt_dn7=cnt_dn7, cnt_up7=cnt_up7)
    json.dump(dict(liq=liq.tolist(), liq_half=liq_half.tolist(), perps=len(P), x=X_LEVELS, k=K_LEVELS),
              open(f"{TMP}/liq_{per}.json", "w"))
    print(per, "перпов", len(P), "событий", len(E), f"{time.time() - tic:.0f} с", flush=True)


if __name__ == "__main__":
    for per in sys.argv[1:]:
        build(per)
