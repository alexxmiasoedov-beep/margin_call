"""Два года (19.10.2024–18.10.2026): 15-мин свечи всех USDT-M фьючерсов Binance, включая делистингованные (список — из архива),
причинное обнаружение пампов (как в pump_short6m.detect, но векторно) → окна свечей вокруг каждого пампа → mm2/pumps2y.pkl."""
import re, subprocess, datetime, pickle, sys
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as sw
from concurrent.futures import ThreadPoolExecutor
import bv
UTC = datetime.timezone.utc
T0 = datetime.datetime(2024, 10, 19, tzinfo=datetime.timezone(datetime.timedelta(hours=3))).timestamp()
T1 = datetime.datetime(2026, 10, 19, tzinfo=datetime.timezone(datetime.timedelta(hours=3))).timestamp()
MONTHS = [f"2024-{m:02d}" for m in (10, 11, 12)] + [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]
DAYS = [f"2026-10-{d:02d}" for d in range(1, 19)]
def detect(k, thr=0.15):
    c, h = k[:, 4], k[:, 2]; n = len(k)
    calm = np.zeros(n, bool); calm[8:] = np.abs(c[8:] / c[:-8] - 1) <= 0.05
    base = np.full(n, -1)
    for L in range(8, 0, -1):                                    # меньший L (более поздняя база) перезаписывает
        if n < L: continue
        rm = np.full(n, -np.inf); rm[L - 1:] = sw(h, L).max(1)
        i = np.arange(n) - L; ic = np.clip(i, 0, n - 1)
        ok = (i >= 8) & calm[ic] & (rm >= c[ic] * (1 + thr)); base[ok] = i[ok]
    out, last = [], -10**9
    for j in np.flatnonzero(base >= 0):
        if j < 9 or j > n - 2 or j - last < 96: continue
        out.append((int(j), int(base[j]))); last = j
    return out
def symbols():
    syms, marker = [], ""
    while True:
        x = subprocess.run(["curl", "-sS", "-m", "60", f"https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=data/futures/um/monthly/klines/&delimiter=/&marker={marker}"],
                           capture_output=True, text=True).stdout
        got = re.findall(r"klines/([A-Z0-9]+)/</Prefix>", x); syms += got
        if "<IsTruncated>true" not in x or not got: break
        marker = f"data/futures/um/monthly/klines/{got[-1]}/"
    return sorted({s[:-4] for s in syms if s.endswith("USDT")})
def one(s):
    try: k = bv.kfull(s, "klines", "15m", MONTHS, DAYS)
    except Exception: return s, None, []
    if k is None or len(k) < 200: return s, None, []
    ev = []
    for j, i in detect(k):
        t_in = k[j, 0] + 900
        if not (T0 <= t_in < T1): continue
        a, b = max(0, j - 100), min(len(k), j + 300)
        ev.append(dict(s=s, j=j - a, i=i - a, t_in=t_in, w=k[a:b][:, [0, 2, 3, 4, 6]].copy(), end=b == len(k)))
    return s, (k[0, 0], k[-1, 0], len(k)), ev
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":                # сверка с циклической версией на 6,5 месяцах
        from pump_short6m import K, detect as det_loop
        bad = sum(det_loop(K[s]) != detect(K[s]) for s in list(K)[:150]); print("расхождений на 150 монетах:", bad); sys.exit()
    S = symbols(); print("символов USDT-M в архиве:", len(S), flush=True)
    EV, INFO = [], {}
    with ThreadPoolExecutor(16) as ex:
        for n, (s, info, ev) in enumerate(ex.map(one, S)):
            if info: INFO[s] = info; EV += ev
            if n % 100 == 0: print(datetime.datetime.now().strftime("%H:%M:%S"), n, s, "пампов пока", len(EV), flush=True)
    pickle.dump(dict(EV=EV, INFO=INFO), open("mm2/pumps2y.pkl", "wb"))
    print("монет со свечами:", len(INFO), "| пампов за 2 года:", len(EV), "у", len({e["s"] for e in EV}), "монет", flush=True)
