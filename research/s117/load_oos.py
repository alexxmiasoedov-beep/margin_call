"""s117 — независимая выборка: 15-мин свечи и фандинг всех USDT-M перпов Binance (включая снятые с торгов — список из
листинга архива) за 01.10.2022–30.09.2024 (MC_Y0=2020 — 01.10.2020–30.09.2022, файлы *_2020.pkl), в формате s2/k2y.pkl и s2/fund2y.pkl, → s117/k_oos.pkl, s117/fund_oos.pkl.
Как s2/load_full.py (research/futures/bv.py, кэш архива — cache/), плюс каждая монета дополнена до общей сетки по BTC:
свечи до начала торгов и после снятия — заглушки без объёма с последней ценой (как в k2y). Запуск из папки с данными:
python3 <repo>/research/s117/load_oos.py"""
import datetime
import os
import pickle
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "futures"))
import bv  # noqa: E402

Y0 = int(os.environ.get("MC_Y0", "2022"))                 # начало периода: октябрь года Y0 … сентябрь Y0 + 2 (s120: 2020)
MONTHS = [f"{Y0}-{m:02d}" for m in (10, 11, 12)] + [f"{Y0 + 1}-{m:02d}" for m in range(1, 13)] + \
         [f"{Y0 + 2}-{m:02d}" for m in range(1, 10)]
SUF = "oos" if Y0 == 2022 else str(Y0)


def symbols():
    syms, marker = [], ""
    while True:
        x = subprocess.run(["curl", "-sS", "-m", "60", "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix="
                            f"data/futures/um/monthly/klines/&delimiter=/&marker={marker}"], capture_output=True, text=True).stdout
        got = re.findall(r"klines/([A-Z0-9]+)/</Prefix>", x); syms += got
        if "<IsTruncated>true" not in x or not got:
            break
        marker = f"data/futures/um/monthly/klines/{got[-1]}/"
    return sorted({s[:-4] for s in syms if s.endswith("USDT")})


def one(s):
    try:
        k = bv.kfull(s, "klines", "15m", MONTHS)
    except Exception:
        k = None
    if k is None or len(k) < 96 * 3:
        return s, None, None
    arr = dict(t=k[:, 0].astype(np.int64), o=k[:, 1].astype(np.float32), h=k[:, 2].astype(np.float32),
               l=k[:, 3].astype(np.float32), c=k[:, 4].astype(np.float32), qv=k[:, 6].astype(np.float32),
               tb=k[:, 8].astype(np.float32), n=k[:, 7].astype(np.float32))
    fr = []
    for m in MONTHS:
        for p in bv.rows(bv.fetch(f"monthly/fundingRate/{s}USDT/{s}USDT-fundingRate-{m}.zip")):
            try:
                fr.append((int(p[0]) // 1000, float(p[1]), float(p[2])))
            except (ValueError, IndexError):
                pass
    return s, arr, np.array(sorted(fr)) if fr else None


def pad(K):
    g = K["BTC"]["t"]
    for s, a in K.items():
        if len(a["t"]) == len(g) and (a["t"] == g).all():
            continue
        idx = np.searchsorted(g, a["t"]); ok = (idx < len(g)) & (g[np.minimum(idx, len(g) - 1)] == a["t"])
        out = {}
        pos = np.full(len(g), -1); pos[idx[ok]] = np.flatnonzero(ok)
        filled = np.maximum.accumulate(np.where(pos >= 0, np.arange(len(g)), -1))
        first = np.flatnonzero(pos >= 0)[0]
        src = np.where(filled >= 0, pos[np.maximum(filled, 0)], pos[first])
        for col in ("o", "h", "l", "c"):
            cl = a["c"][src]
            out[col] = np.where(pos >= 0, a[col][np.maximum(pos, 0)], cl).astype(np.float32)
        for col in ("qv", "tb", "n"):
            out[col] = np.where(pos >= 0, a[col][np.maximum(pos, 0)], 0).astype(np.float32)
        out["t"] = g.copy()
        K[s] = out
    return K


def main():
    S = symbols()
    print("символов в архиве:", len(S), flush=True)
    K, F = {}, {}
    with ThreadPoolExecutor(16) as ex:
        for n, (s, a, f) in enumerate(ex.map(one, S)):
            if a is not None:
                K[s] = a
            if f is not None:
                F[s] = f
            if n % 100 == 0:
                print(datetime.datetime.now().strftime("%H:%M:%S"), n, len(K), flush=True)
    K = pad(K)
    pickle.dump(K, open(f"s117/k_{SUF}.pkl", "wb"), protocol=4)
    pickle.dump(F, open(f"s117/fund_{SUF}.pkl", "wb"), protocol=4)
    print("монет", len(K), "| свечей на монету", len(K["BTC"]["t"]), "| с фандингом", len(F), flush=True)


if __name__ == "__main__":
    main()
