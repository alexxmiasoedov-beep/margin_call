"""s278 — общее: часовая сетка «перп × час» (закрытие перпа на конце часа и оборот часа) и обороты площадок в $
по тем же часам. Доходы сделок здесь не считаются — только обороты, доли и скачки цены перпа (частоты событий).

Периоды:
- P1 «2024–2026»: 01.10.2024–18.10.2026 (общее окно всех площадок), перпы s224/k_d.pkl;
- P0 «2022–2024»: 01.10.2022–01.10.2024, перпы s117/k_oos.pkl (327 перпов выборки s117);
- P00 «2020–2022»: 01.10.2020–01.10.2022, перпы s117/k_2020.pkl — только Upbit и Bithumb (корейский контроль);
- PF «04–19.11.2026»: свежий отрезок, где есть HTX и MEXC (их API отдаёт только последние 2000 и 500 часов).

Площадки (оборот в $ за час; час — по началу, UTC):
- upbit, bithumb — s15/kr_candles_*.pkl (P1), s88/oos/kc (P0); вона → $ по KRW-USDT биржи (P1) или KRW-BTC Upbit к BTC (P0);
- indodax, bitkub, coindcx — s93/c (P1); местная валюта → $ по паре USDT той же биржи;
- btcturk — s75/btcturk1h.pkl, binance_try — s67/try1h.pkl (P1); лира → $ по USDTTRY Binance;
- coinbase — s46/cb1h.pkl, bitvavo — s68/bvv1h.pkl (евро → $ по EURUSDT за сутки), binance_spot — s23/spot1h.pkl (P1)
  и архив data.binance.vision (P0, fetch_bspot_p0.py);
- okx, bitget, kucoin, gate, htx, mexc — /dev/shm/s278/raw (fetch_venues.py), пары к USDT;
- bitbank, gmo — выборка дней (fetch_japan.py), иена → $ по USDT/JPY bitbank.
Монета площадки сопоставляется с перпом по тикеру (1000PEPE → PEPE) и проверяется по цене: медиана отношения цены
площадки в $ к цене перпа 0,8–1,25 (если у площадки есть цена).

Запуск скриптов — из /home/user/mc_data (python3 -I <repo>/research/s278/study/<скрипт>.py)."""
import glob
import json
import os
import pickle
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "s259", "study"))
from common259 import base, crypto_perps  # noqa: E402

H, DAY = 3600, 86400
MONTH = 30.44 * DAY
TMP = "/dev/shm/s278"
OUT = "/home/user/mc_data/s278"
os.makedirs(TMP, exist_ok=True)
os.makedirs(OUT, exist_ok=True)


def ts(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp())


PER = {
    "P1": dict(name="2024–2026", k="s224/k_d.pkl", t0=ts("2024-10-01"), t1=ts("2026-10-18"), mid=ts("2025-10-01")),
    "P0": dict(name="2022–2024", k="s117/k_oos.pkl", t0=ts("2022-10-01"), t1=ts("2024-10-01"), mid=ts("2023-10-01")),
    # только корейский контроль: обнуление Upbit на третьем периоде (s88/oos2020)
    "P00": dict(name="2020–2022", k="s117/k_2020.pkl", t0=ts("2020-10-01"), t1=ts("2022-10-01"), mid=ts("2021-10-01")),
    # свежий отрезок, где есть HTX и MEXC (их API отдаёт только последние 2000 и 500 часов); Кореи и спота Binance нет
    "PF": dict(name="04–19.11.2026", k="s224/k_d.pkl", t0=ts("2026-11-04"), t1=ts("2026-11-19"), mid=ts("2026-11-12")),
}

VENUES = {
    "P1": ["upbit", "bithumb", "okx", "bitget", "kucoin", "gate", "htx", "mexc", "binance_spot", "indodax", "bitkub",
           "coindcx", "btcturk", "binance_try", "coinbase", "bitvavo", "bitbank", "gmo"],
    "P0": ["upbit", "bithumb", "okx", "bitget", "kucoin", "binance_spot"],
    "PF": ["okx", "bitget", "kucoin", "gate", "htx", "mexc"],
    "P00": ["upbit", "bithumb"],
}
NAME = {"upbit": "Upbit", "bithumb": "Bithumb", "okx": "OKX", "bitget": "Bitget", "kucoin": "KuCoin", "gate": "Gate",
        "htx": "HTX", "mexc": "MEXC", "binance_spot": "спот Binance", "indodax": "Indodax", "bitkub": "Bitkub",
        "coindcx": "CoinDCX", "btcturk": "BTCTurk", "binance_try": "Binance TRY", "coinbase": "Coinbase",
        "bitvavo": "Bitvavo", "bitbank": "bitbank", "gmo": "GMO Coin"}
# группы площадок: страна / язык розницы
GROUPS = {
    "KR": ["upbit", "bithumb"],
    "CN4": ["okx", "bitget", "kucoin", "gate"],
    "CN2": ["okx", "bitget"],
    "SEA": ["indodax", "bitkub"],
    "IN": ["coindcx"],
    "TR": ["btcturk", "binance_try"],
    "US": ["coinbase"],
    "EU": ["bitvavo"],
    "BS": ["binance_spot"],
}
GNAME = {"KR": "Корея (Upbit + Bithumb)", "CN4": "OKX + Bitget + KuCoin + Gate", "CN2": "OKX + Bitget",
         "SEA": "Индонезия + Таиланд (Indodax + Bitkub)", "IN": "Индия (CoinDCX)", "TR": "Турция (BTCTurk + Binance TRY)",
         "US": "США (Coinbase)", "EU": "Европа (Bitvavo)", "BS": "спот Binance"}
MULT_RE = re.compile(r"^(1000000|100000|10000|1000|1M)(.+)$")
SAMPLED = {"bitbank", "gmo"}                                  # японские биржи — выборка дней (fetch_japan.py)


def mult(p):
    m = MULT_RE.match(p)
    if not m or m.group(2)[0].isdigit():
        return 1.0
    return 1e6 if m.group(1) == "1M" else float(m.group(1))


# ---------------- перпы ----------------

def perp_hourly(per):
    """C — закрытие на конце часа k (час k начинается в t0 + k·H), Q — оборот часа $, F — время первой свечи с оборотом."""
    cache = f"{TMP}/perp_{per}.npz"
    if os.path.exists(cache):
        z = np.load(cache, allow_pickle=True)
        return list(z["P"]), z["C"], z["Q"], z["F"]
    cfg = PER[per]
    t0, t1 = cfg["t0"], cfg["t1"]
    n = (t1 - t0) // H
    K = pickle.load(open(cfg["k"], "rb"))
    P = crypto_perps(K)
    C = np.full((len(P), n), np.nan, np.float64)
    Q = np.zeros((len(P), n), np.float32)
    F = np.full(len(P), np.nan)
    for i, p in enumerate(P):
        a = K[p]
        t = a["t"].astype(np.int64)
        nz = np.flatnonzero(a["qv"] > 0)
        if len(nz):
            F[i] = float(t[nz[0]])
        m = (t >= t0) & (t < t1)
        if not m.any():
            continue
        tt = t[m]
        k = (tt - t0) // H
        np.add.at(Q[i], k, a["qv"][m].astype(np.float64))
        lb = (tt - t0) % H == 3 * 900
        C[i, k[lb]] = a["c"][m][lb]
    del K
    np.savez(cache, P=np.array(P, dtype=object), C=C, Q=Q, F=F)
    return P, C, Q, F


# ---------------- площадки ----------------

def _ffill_rate(t_rate, r_rate, t):
    """Курс на час t: последнее известное значение не позже t (иначе первое)."""
    i = np.searchsorted(t_rate, t, side="right") - 1
    i = np.clip(i, 0, len(t_rate) - 1)
    return r_rate[i]


def load_venue(ven, per):
    """{монета: (t начала часа, оборот $, цена $ или None)}."""
    out = {}
    if ven in ("upbit", "bithumb") and per == "P1":
        X = pickle.load(open(f"s15/kr_candles_{ven}.pkl", "rb"))
        u = X["USDT"]
        tr, rr = u["t"].astype(np.int64), u["c"].astype(np.float64)
        for b, x in X.items():
            if b == "USDT" or not len(x["t"]):
                continue
            t = x["t"].astype(np.int64)
            r = _ffill_rate(tr, rr, t)
            out[b] = (t, x["v"].astype(np.float64) / r, x["c"].astype(np.float64) / r)
    elif ven in ("upbit", "bithumb") and per in ("P0", "P00"):
        kc = "s88/oos/kc" if per == "P0" else "s88/oos2020/kc"
        btc = pickle.load(open(f"{kc}/upbit/KRW-BTC.pkl", "rb"))
        Pp, C, Q, F = perp_hourly(per)
        cb = C[Pp.index("BTC")]                                # BTC перпа на конце часа k
        t0, n = PER[per]["t0"], C.shape[1]
        bt, bc = btc["t"].astype(np.int64), btc["c"].astype(np.float64)
        # курс воны: закрытие KRW-BTC Upbit за час / закрытие BTCUSDT перпа за тот же час
        k = (bt - t0) // H
        good = (k >= 0) & (k < n) & ((bt - t0) % H == 0)
        good[good] &= np.isfinite(cb[k[good]])
        rt = bt[good]
        rr = bc[good] / cb[k[good]]
        for f in glob.glob(f"{kc}/{ven}/KRW-*.pkl"):
            x = pickle.load(open(f, "rb"))
            if x is None or not len(x["t"]):
                continue
            b = os.path.basename(f)[4:-4]
            t = x["t"].astype(np.int64)
            r = _ffill_rate(rt, rr, t)
            out[b] = (t, x["v"].astype(np.float64) / r, x["c"].astype(np.float64) / r)
    elif ven in ("indodax", "bitkub", "coindcx"):
        fs = {os.path.basename(f)[:-4]: f for f in glob.glob(f"s93/c/{ven}/*.pkl")}
        u = pickle.load(open(fs["USDT"], "rb"))
        tr, rr = u[:, 0].astype(np.int64), u[:, 1].astype(np.float64)
        for b, f in fs.items():
            if b == "USDT":
                continue
            a = pickle.load(open(f, "rb"))
            if not len(a):
                continue
            t = a[:, 0].astype(np.int64)
            r = _ffill_rate(tr, rr, t)
            out[b] = (t, a[:, 1] * a[:, 2] / r, a[:, 1] / r)
    elif ven == "binance_try":
        X = pickle.load(open("s67/try1h.pkl", "rb"))
        u = X["USDTTRY"]
        tr, rr = u[:, 0].astype(np.int64), u[:, 2].astype(np.float64)
        for pair, a in X.items():
            if pair == "USDTTRY" or not pair.endswith("TRY") or not len(a):
                continue
            t = a[:, 0].astype(np.int64)
            r = _ffill_rate(tr, rr, t)
            out[pair[:-3]] = (t, a[:, 1] / r, a[:, 2] / r)
    elif ven == "btcturk":
        X = pickle.load(open("s75/btcturk1h.pkl", "rb"))
        u = pickle.load(open("s67/try1h.pkl", "rb"))["USDTTRY"]
        tr, rr = u[:, 0].astype(np.int64), u[:, 2].astype(np.float64)
        for pair, a in X.items():
            if pair == "USDTTRY" or not pair.endswith("TRY") or not len(a):
                continue
            t = a[:, 0].astype(np.int64)
            out[pair[:-3]] = (t, a[:, 1] / _ffill_rate(tr, rr, t), None)
    elif ven == "coinbase":
        X = pickle.load(open("s46/cb1h.pkl", "rb"))
        for b, d in X.items():
            if not len(d):
                continue
            out[b] = (d["T"].values.astype(np.int64) - H, d["usd"].values.astype(np.float64), d["c"].values.astype(np.float64))
    elif ven == "bitvavo":
        X = pickle.load(open("s68/bvv1h.pkl", "rb"))
        fx = json.load(open(f"{TMP}/fx/eurusdt_1d_a.json")) + json.load(open(f"{TMP}/fx/eurusdt_1d_b.json"))
        ft = np.array([int(r[0]) // 1000 for r in fx], np.int64)
        fr = np.array([float(r[4]) for r in fx])
        o = np.argsort(ft)
        ft, fr = ft[o], fr[o]
        for b, d in X.items():
            if not len(d):
                continue
            t = d["T"].values.astype(np.int64) - H
            out[b] = (t, d["eur"].values.astype(np.float64) * _ffill_rate(ft, fr, t - DAY), None)
    elif ven == "binance_spot" and per == "P0":                 # 2022–2024: архив data.binance.vision (fetch_bspot_p0.py)
        for f in glob.glob(f"{TMP}/raw/binance_spot/P0/*.npz"):
            if f.endswith(".tmp.npz"):
                continue
            z = np.load(f)
            if len(z["t"]):
                out["@" + os.path.basename(f)[:-4]] = (z["t"].astype(np.int64), z["qv"].astype(np.float64),
                                                       z["c"].astype(np.float64))
    elif ven == "binance_spot":
        X = pickle.load(open("s23/spot1h.pkl", "rb"))
        for p, a in X.items():
            if not len(a):
                continue
            out["@" + p] = (a[:, 0].astype(np.int64), a[:, 1].astype(np.float64), a[:, 4].astype(np.float64))
    elif ven in ("okx", "bitget", "kucoin", "gate", "htx", "mexc"):
        for f in glob.glob(f"{TMP}/raw/{ven}/{'P1' if per == 'PF' else per}/*.npz"):
            if f.endswith(".tmp.npz"):
                continue
            z = np.load(f)
            if not len(z["t"]):
                continue
            out[os.path.basename(f)[:-4]] = (z["t"].astype(np.int64), z["qv"].astype(np.float64), z["c"].astype(np.float64))
    elif ven in ("bitbank", "gmo"):
        f = f"{TMP}/japan/{ven}.pkl"
        if os.path.exists(f):
            out = pickle.load(open(f, "rb"))
    return out


def align(ven, per, P, C):
    """V[i, k] — оборот площадки в $ за час k по перпу P[i] (NaN — пары нет или вне её истории). Проверка цены."""
    cfg = PER[per]
    t0, n = cfg["t0"], C.shape[1]
    X = load_venue(ven, per)
    V = np.full((len(P), n), np.nan, np.float32)
    info = dict(matched=0, price_bad=[], no_price=0)
    for i, p in enumerate(P):
        x = X.get("@" + p) if ven == "binance_spot" else X.get(base(p))
        if x is None:
            continue
        t, v, c = x
        m = (t >= t0) & (t < t0 + n * H) & ((t - t0) % H == 0)
        if not m.any():
            continue
        k = ((t[m] - t0) // H).astype(np.int64)
        lo, hi = k.min(), k.max()
        # проверка цены: медиана отношения (цена площадки × множитель) / цена перпа на конце часа
        if c is not None:
            pc = C[i, k]
            ok = np.isfinite(pc) & (pc > 0) & np.isfinite(c[m]) & (c[m] > 0)
            if ok.sum() >= 24:
                ratio = np.median(c[m][ok] / pc[ok])
                # площадка может торговать ту же монету с множителем, как перп (1000CAT на споте Binance)
                if not (0.8 <= ratio * mult(p) <= 1.25 or 0.8 <= ratio <= 1.25):
                    info["price_bad"].append((p, round(float(ratio * mult(p)), 3)))
                    continue
        else:
            info["no_price"] += 1
        if ven in SAMPLED:                                     # выборка дней: часы вне выборки — NaN, а не ноль
            V[i, k] = np.nan_to_num(v[m])
        else:
            row = np.zeros(hi - lo + 1, np.float64)
            np.add.at(row, k - lo, np.nan_to_num(v[m]))
            V[i, lo:hi + 1] = row
        info["matched"] += 1
    return V, info


def panel(per, venues=None):
    """Перпы и обороты площадок периода; кэш в /dev/shm/s278/venue_<период>_<площадка>.npz (пересобирается с rebuild)."""
    P, C, Q, F = perp_hourly(per)
    venues = venues or VENUES[per]
    VV, INFO = {}, {}
    rb = next((a[8:].split(",") for a in sys.argv if a.startswith("rebuild=")), [])   # rebuild=okx,bitget
    for ven in venues:
        f = f"{TMP}/venue_{per}_{ven}.npz"
        fi = f"{TMP}/venue_{per}_{ven}.json"
        if os.path.exists(f) and "rebuild" not in sys.argv and ven not in rb:
            VV[ven] = np.load(f)["V"]
            INFO[ven] = json.load(open(fi))
            continue
        V, info = align(ven, per, P, C)
        np.savez_compressed(f, V=V)
        json.dump(info, open(fi, "w"))
        VV[ven], INFO[ven] = V, info
    return P, C, Q, F, VV, INFO
