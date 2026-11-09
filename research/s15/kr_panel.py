"""Часовая панель «монета × час» для монет с фьючерсом Binance, торгующихся к воне на Upbit или Bithumb:
- доля Кореи (Upbit + Bithumb, вона → доллар по KRW-USDT той же биржи) в обороте за час вместе с фьючерсом Binance;
- её обычный уровень — медиана часовых долей за 7 суток до часа;
- премия Кореи к цене фьючерса (средняя по оборотам бирж);
- рост фьючерса за 1, 2 и 4 ч; пампы 🇰🇷 по 15-мин свечам (+15% за ≤ 2 ч из покоя, как scanner._pump_times).
Результат — s15/kr_panel.pkl: {фьючерс: DataFrame по часам}, s15/kr_pumps.pkl: {фьючерс: индексы 15-мин свечей пампов}.

Запуск из папки с данными (после kr_candles.py): python3 s15/kr_panel.py"""
import glob
import os
import pickle
import sys
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import K, fut_of, live

EXS = ("upbit", "bithumb")


def pumps(a):
    """Индексы 15-мин свечей, где впервые достигнуто +15% от базы за ≤ 8 свечей; база спокойна (±5% за 2 ч до неё);
    не чаще раза в сутки — как scanner._pump_times."""
    c, h = a["c"].astype(float), a["h"].astype(float)
    n = len(c)
    calm = np.zeros(n, bool)
    calm[8:] = np.abs(c[8:] / c[:-8] - 1) <= 0.05
    hit = np.zeros(n, bool)
    hs = pd.Series(h)
    for L in range(1, 9):                                     # база i = j − L, максимум свечей i+1…j
        mx = hs.rolling(L, min_periods=L).max().values
        base = np.r_[np.full(L, np.nan), c[:-L]]
        cb = np.r_[np.zeros(L, bool), calm[:-L]]
        hit |= cb & (mx >= base * 1.15) & (np.arange(n) - L >= 8)
    nz = np.flatnonzero(a["qv"] > 0)
    if not len(nz):
        return np.array([], dtype=np.int64)
    hit &= (np.arange(n) >= nz[0] + 96) & (np.arange(n) <= nz[-1])   # фьючерс торгуется ≥ суток, не после делистинга
    hit &= a["qv"] > 0
    out, last = [], -10 ** 9
    for j in np.flatnonzero(hit):
        if j - last >= 96:
            out.append(int(j)); last = j
    return np.array(out, dtype=np.int64)


def coin(b, C, rate):
    s, mult = fut_of(b)
    a = K[s]; t = a["t"]
    j = np.flatnonzero((t + 900) % 3600 == 0)                 # 15-мин свечи, закрывающиеся в начале часа
    j = j[j >= 16]
    j = j[t[j - 3] == t[j] - 2700]
    T = t[j] + 900; H = T - 3600
    cs = np.r_[0.0, np.cumsum(a["qv"].astype(float))]
    bvol = cs[j + 1] - cs[j - 3]
    c = a["c"].astype(float)
    kv = np.zeros(len(j)); pw = np.zeros(len(j)); pv = np.zeros(len(j)); first = np.inf
    for ex in EXS:
        x = C[ex].get(b)
        if x is None or not len(x["t"]):
            continue
        first = min(first, float(x["t"][0]))
        i = np.searchsorted(x["t"], H); i2 = np.minimum(i, len(x["t"]) - 1)
        ok = (i < len(x["t"])) & (x["t"][i2] == H)
        r = rate[ex](H)
        v = np.where(ok, x["v"][i2].astype(float) / r, 0.0)
        p = np.where(ok, x["c"][i2].astype(float) * mult / r / c[j] - 1, 0.0)
        kv += v; pw += p * v; pv += v
    keep = (H >= first) & (bvol > 0)                          # фьючерс торговался в этот час (не заглушка)
    d = pd.DataFrame({"T": T, "j": j, "kr": kv, "bin": bvol, "prem": np.where(pv > 0, pw / np.maximum(pv, 1e-9), np.nan)})[keep]
    d["share"] = d.kr / (d.kr + d.bin).clip(lower=1.0)
    d["norm"] = d.share.shift(1).rolling(168, min_periods=120).median()
    jj = d.j.values
    for hh in (1, 2, 4, 24):
        d[f"r{hh}"] = c[jj] / c[np.maximum(jj - 4 * hh, 0)] - 1
    return s, d.reset_index(drop=True)


def load(ex):
    """Свечи биржи: общий файл kr_candles.py или, пока сбор идёт, кэш по рынкам s15/kc/<биржа>/."""
    p = f"s15/kr_candles_{ex}.pkl"
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    return {os.path.basename(f)[4:-4]: x for f in sorted(glob.glob(f"s15/kc/{ex}/KRW-*.pkl")) if (x := pickle.load(open(f, "rb")))}


if __name__ == "__main__":
    C = {ex: load(ex) for ex in EXS}
    C = {ex: c if "USDT" in c else {} for ex, c in C.items()}            # без курса KRW-USDT биржу не считаем
    rate = {}
    for ex in [e for e in EXS if C[e]]:
        u = C[ex]["USDT"]
        ser = pd.Series(u["c"].astype(float), index=u["t"])
        rate[ex] = (lambda ser: lambda H: ser.reindex(np.union1d(ser.index, H)).ffill().bfill().reindex(H).values)(ser)
    coins = sorted({b for ex in EXS for b in C[ex] if b != "USDT" and fut_of(b)[0]})
    P, PU = {}, {}
    for b in coins:
        s, d = coin(b, C, rate)
        if len(d) >= 24 * 14:
            P[s] = d
    for s in K:
        PU[s] = pumps(K[s])
    pickle.dump(P, open("s15/kr_panel.pkl", "wb")); pickle.dump(PU, open("s15/kr_pumps.pkl", "wb"))
    n = sum(len(d) for d in P.values())
    print(f"монет в панели {len(P)}, строк {n:,}; пампов 🇰🇷-типа по всем фьючерсам {sum(len(v) for v in PU.values()):,}")
