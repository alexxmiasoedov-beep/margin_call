"""s187 — часовые и 4-часовые свечи ликвидных альтов из 15-мин свечей перпов Binance USDT-M (только свечи с оборотом).

Вселенная периода: монеты, у которых хотя бы в одну неделю стоял флаг ликвидности s183 (`liq5`: оборот перпа ≥ 5 млн $
в сутки за 7 сут, перп ≥ 30 сут; акции, металлы, стейблкоины уже исключены), без BTC и ETH. Неделя ликвидности —
[понедельник d0, d0 + 7 сут) по срезу s183 (признаки — по данным до d0).

Свеча 1h/4h — по сетке UTC (4h: 00, 04, …, 20), из живых 15-мин свечей: o — первая, h — max, l — min, c — последняя,
qv — сумма оборота $, v — объём в монетах ≈ Σ qv / ((h + l + c) / 3) по 15-мин свечам (в архиве нет объёма в монетах),
nb — число живых 15-мин свечей (4 или 16 у полной свечи).

Запуск: python3 bars.py → /home/user/mc_data/s187/bars_<период>.pkl:
{"1h": {монета: {t, o, h, l, c, v, qv, nb}}, "4h": {…}, "liq": DataFrame[s, d0], "t0", "t1"}; t — начало свечи (сек)."""
import os
import pickle
import sys

import numpy as np
import pandas as pd

D = "/home/user/mc_data"
OUT = f"{D}/s187"
PER = {
    "2020–2022": (f"{D}/s117/k_2020.pkl", "2020-10-01", "2022-10-01"),
    "2022–2024": (f"{D}/s117/k_oos.pkl", "2022-10-01", "2024-10-01"),
    "2024–2026": (f"{D}/s2/k2y.pkl", "2024-10-01", "2026-10-19"),
}
TF = {"1h": 3600, "4h": 14400}


def ts(x):
    return int(pd.Timestamp(x, tz="UTC").timestamp())


def liquid_weeks(per):
    X = pd.read_pickle(f"{D}/s183/feat2_{per}.pkl")
    L = X[X.liq5.astype(bool) & ~X.s.isin(["BTC", "ETH"])][["s", "d0"]].copy()
    L["d0"] = L.d0.astype(np.int64)
    return L.reset_index(drop=True)


def aggregate(a, sec):
    qv = np.asarray(a["qv"], np.float64)
    live = qv > 0
    if live.sum() < 8:
        return None
    t = np.asarray(a["t"], np.int64)[live]
    o = np.asarray(a["o"], np.float64)[live]
    h = np.asarray(a["h"], np.float64)[live]
    l_ = np.asarray(a["l"], np.float64)[live]
    c = np.asarray(a["c"], np.float64)[live]
    qv = qv[live]
    tp = (h + l_ + c) / 3.0
    vb = np.where(tp > 0, qv / tp, 0.0)
    g = t // sec
    st = np.r_[0, np.flatnonzero(np.diff(g)) + 1]
    en = np.r_[st[1:], len(t)] - 1
    return {
        "t": (g[st] * sec).astype(np.int64),
        "o": o[st].astype(np.float32), "h": np.maximum.reduceat(h, st).astype(np.float32),
        "l": np.minimum.reduceat(l_, st).astype(np.float32), "c": c[en].astype(np.float32),
        "v": np.add.reduceat(vb, st).astype(np.float32), "qv": np.add.reduceat(qv, st).astype(np.float32),
        "nb": np.diff(np.r_[st, len(t)]).astype(np.int8),
    }


def build(per):
    kp, t0, t1 = PER[per]
    L = liquid_weeks(per)
    uni = sorted(set(L.s))
    K = pickle.load(open(kp, "rb"))
    out = {"1h": {}, "4h": {}, "liq": L, "t0": ts(t0), "t1": ts(t1)}
    miss = []
    for s in uni:
        if s not in K:
            miss.append(s)
            continue
        for tf, sec in TF.items():
            b = aggregate(K[s], sec)
            if b is not None:
                out[tf][s] = b
    del K
    pickle.dump(out, open(f"{OUT}/bars_{per}.pkl", "wb"), protocol=5)
    n1 = sum(len(v["t"]) for v in out["1h"].values())
    print(f"{per}: монет {len(uni)}, нет в свечах {len(miss)} {miss[:10]}, свечей 1h {n1}, "
          f"4h {sum(len(v['t']) for v in out['4h'].values())}, недель-монет ликвидности {len(L)}", flush=True)


if __name__ == "__main__":
    for p in (sys.argv[1:] or list(PER)):
        build(p)
