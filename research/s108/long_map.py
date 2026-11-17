"""s108 — карта лонга: базовый дрейф альтов на перпах Binance и где у лонга попутный ветер. Дневная панель (00:00 UTC):
ликвидные альты (оборот ≥ 5 млн $ в сутки за 7 сут, фьючерс старше 30 сут; без BTC, ETH, стейблкоинов, акций и сырья).
Доход лонга за 1 и 7 сут от закрытия в 00:00: цена − комиссия 0,1% + полученный фандинг (без стопов). Признаки — только из
данных до входа. Разбор по признакам — ТОЛЬКО на первой половине (вход и выход до 01.12.2025): по нему выбираются
гипотезы, вторая половина остаётся для проверки. Запуск из папки с данными после s103/beta.py:
python3 <repo>/research/s108/long_map.py"""
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ("s15", "s43", "s103", "s105"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
from common import K, funding, live  # noqa: E402
from oi_test import CUT, DAY, ct  # noqa: E402
from beta import index  # noqa: E402
from jumps_test import SKIP  # noqa: E402

KRW = 1400.0


def kr_turnover():
    """Корейский оборот в $ по часам: {монета: (часы, оборот)} — Upbit + Bithumb."""
    out = {}
    for f in ("s15/kr_candles_upbit.pkl", "s15/kr_candles_bithumb.pkl"):
        for c, a in pickle.load(open(f, "rb")).items():
            t = np.asarray(a["t"], np.int64); v = np.asarray(a["v"], float) * np.asarray(a["c"], float) / KRW
            s = pd.Series(v, index=t)
            out[c] = out[c].add(s, fill_value=0) if c in out else s
    return out


def main():
    tI, I, _, _ = index()
    t = K["BTC"]["t"]; close = t + 900
    KR = kr_turnover()
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    days = np.arange((int(close[0]) // DAY + 31) * DAY, (int(close[-1]) // DAY - 7) * DAY, DAY)
    idx_pos = {int(d): int(np.searchsorted(close, d)) for d in days}
    Ic = pd.Series(I); sma20 = Ic.rolling(20 * 96).mean().values
    rows = []
    for s in K:
        if s in SKIP or len(K[s]["t"]) != len(t):
            continue
        a = K[s]; c = a["c"].astype(float); qv = a["qv"].astype(float)
        lo, hi = live(s)
        fr = funding(s)
        base = re.sub(r"^(1000000|100000|10000|1000)", "", s)
        kr = KR.get(base); sp = SP.get(base)
        if sp is not None:
            spt = sp[:, 0].astype(np.int64); spt = np.where(spt > 1e11, spt // 1000, spt); spq = pd.Series(sp[:, 1], index=spt)
        for d in days:
            i = idx_pos[int(d)]
            if i + 7 * 96 >= len(t) or close[i] != d or d - 30 * DAY < lo or d + 7 * DAY > hi:
                continue
            v7 = qv[i - 7 * 96 + 1:i + 1].sum() / 7
            if v7 < 5e6 or c[i] <= 0:
                continue
            f_in = lambda a_, b_: float(fr[(fr[:, 0] > a_) & (fr[:, 0] <= b_), 1].sum()) if len(fr) else 0.0
            h = c[i - 7 * 96:i + 1:4]                                  # часовые закрытия за 7 сут
            lr = np.diff(np.log(h))
            d7 = dict(s=s, t=float(d),
                      r1=c[i] / c[i - 96] - 1, r7=c[i] / c[i - 7 * 96] - 1, r30=c[i] / c[i - 30 * 96] - 1,
                      hi30=c[i] / c[i - 30 * 96:i + 1].max() - 1, vol7=lr.std() * np.sqrt(24),
                      fund3=f_in(d - 3 * DAY, d) / 9, age=(d - lo) / DAY, lv=np.log10(v7),
                      idx7=I[i] / I[i - 7 * 96] - 1, idx_up=bool(I[i] > sma20[i]),
                      btc7=K["BTC"]["c"][i] / K["BTC"]["c"][i - 7 * 96] - 1)
            if kr is not None:
                kv = kr[(kr.index >= d - 7 * DAY) & (kr.index < d)].sum() / 7
                d7["krs"] = kv / (kv + v7)
            else:
                d7["krs"] = 0.0
            if sp is not None:
                sv = spq[(spq.index >= d - 7 * DAY) & (spq.index < d)].sum() / 7
                d7["sps"] = sv / (sv + v7)
            else:
                d7["sps"] = np.nan
            for hd in (1, 7):
                j = i + hd * 96
                d7[f"L{hd}"] = c[j] / c[i] - 1 - 0.001 - f_in(d, d + hd * DAY)
            rows.append(d7)
    X = pd.DataFrame(rows)
    X.to_pickle("s108/panel.pkl")
    print(f"строк: {len(X)}, монет: {X.s.nunique()}, дней: {X.t.nunique()}")
    for lab, x in (("1-я половина", X[X.t + 7 * DAY < CUT]), ("2-я половина", X[X.t >= CUT])):
        for hd in (1, 7):
            m, tt, n = ct(x[f"L{hd}"], x.t)
            print(f"  {lab}: лонг каждой ликвидной монеты на {hd} сут — {m:+.2%} (t {tt:+.1f}), в плюсе {(x[f'L{hd}'] > 0).mean():.0%}")
    F = X[X.t + 7 * DAY < CUT]
    print("\nПервая половина: доход лонга на 7 сут по децилям признаков (1 — меньшие значения):")
    for col in ("r1", "r7", "r30", "hi30", "vol7", "fund3", "age", "lv", "krs", "sps", "idx7", "btc7"):
        x = F[F[col].notna()]
        q = pd.qcut(x[col].rank(method="first"), 10, labels=False)
        cells = []
        for k in range(10):
            y = x[q == k]
            m, tt, _ = ct(y.L7, y.t)
            cells.append(f"{m:+5.1%}({tt:+.1f})")
        print(f"  {col:6s} " + " ".join(cells))
    for lab, m in (("индекс альтов выше 20-дн. средней", F.idx_up), ("ниже", ~F.idx_up)):
        y = F[m]; mm, tt, n = ct(y.L7, y.t)
        print(f"  {lab:34s} n={n:6d} {mm:+.2%} (t {tt:+.1f})")


if __name__ == "__main__":
    main()
