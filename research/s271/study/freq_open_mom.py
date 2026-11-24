"""s271 Г5 — частота событий «внутридневной моментум суток UTC»: ход первого часа суток (00:00–01:00 UTC) → сделка в ту же
сторону 23:00–24:00 UTC тех же суток. Доходы не считаются.

Ход первого часа r1 = закрытие свечи 00:45 / закрытие свечи 23:45 прошлых суток − 1. Вселенная суток — 100 перпов с
наибольшим оборотом за прошлые 30 сут (возраст ≥ 30 сут), криптоперпы. Варианты: |r1| ≥ 2 / 3 / 5%; пять крупнейших |r1|
за сутки при |r1| ≥ 2%; рынок — BTC и ETH при |r1| ≥ 0,5 / 1%. Запуск из /home/user/mc_data."""
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common271 import BAR, DAY, PER, TMP, crypto_perps, fmt, freq_line, liquid_rank, load_k  # noqa: E402


def first_hour(a):
    """Сутки D → r1 (ход 23:45 → 01:00 по закрытиям) и наличие свечей последнего часа (23:00–24:00)."""
    t = a["t"].astype(np.int64); c = a["c"].astype(float); q = a["qv"]
    i = np.flatnonzero(t % DAY == 45 * 60)                  # свеча 00:45 (закрытие 01:00)
    i = i[i >= 4]
    i = i[t[i - 4] == t[i] - 4 * BAR]
    ok = (q[i] > 0) & (q[i - 4] > 0) & (c[i - 4] > 0)
    i = i[ok]
    r1 = c[i] / c[i - 4] - 1
    D = t[i] - 45 * 60
    j = i + 92                                                # свеча 23:45 тех же суток (00:45 + 23 ч)
    has_last = (j < len(t)) & (t[np.minimum(j, len(t) - 1)] == D + DAY - BAR)
    return D, r1, has_last


def run(per):
    cfg = PER[per]
    K = load_k(per)
    P = crypto_perps(K)
    cache = f"{TMP}/liq100_{per}.pkl"
    if os.path.exists(cache):
        LR = pickle.load(open(cache, "rb"))
    else:
        LR = liquid_rank(K, P, per, top=100, window=30)
        pickle.dump(LR, open(cache, "wb"))
    rows = []
    for p in P:
        D, r1, hl = first_hour(K[p])
        for d, r, h in zip(D, r1, hl):
            if h and p in LR.get(int(d), ()):
                rows.append((int(d), p, float(r)))
    rows = np.array(rows, dtype=object)
    D = rows[:, 0].astype(np.int64); R = rows[:, 2].astype(float); S = rows[:, 1]
    print(f"\n== {per}: монето-суток во вселенной {len(D)}")
    for thr in (0.02, 0.03, 0.05):
        m = np.abs(R) >= thr
        print(f"|r1| ≥ {thr:.0%}: все {fmt(freq_line(D[m], cfg['t0'], cfg['t1'], cfg['mid'], cfg['tb']))}")
        print(f"         вверх {fmt(freq_line(D[m & (R > 0)], cfg['t0'], cfg['t1'], cfg['mid'], cfg['tb']))}")
        print(f"         вниз  {fmt(freq_line(D[m & (R < 0)], cfg['t0'], cfg['t1'], cfg['mid'], cfg['tb']))}")
        dd = D[m]
        print(f"         суток с событием: {len(np.unique(dd[(dd >= cfg['t0']) & (dd < cfg['t1'])]))}")
    top = []
    for d in np.unique(D):
        k = np.flatnonzero(D == d)
        k = k[np.abs(R[k]) >= 0.02]
        top += list(D[k[np.argsort(-np.abs(R[k]))[:5]]])
    print("пять крупнейших |r1| ≥ 2% за сутки:", fmt(freq_line(top, cfg["t0"], cfg["t1"], cfg["mid"], cfg["tb"])))
    for mk in ("BTC", "ETH"):
        if mk not in K:
            continue
        Dm, rm, hm = first_hour(K[mk])
        for thr in (0.005, 0.01):
            m = hm & (np.abs(rm) >= thr)
            print(f"{mk} |r1| ≥ {thr:.1%}: {fmt(freq_line(Dm[m], cfg['t0'], cfg['t1'], cfg['mid'], cfg['tb']))}")
    del S


if __name__ == "__main__":
    for per in PER:
        run(per)
