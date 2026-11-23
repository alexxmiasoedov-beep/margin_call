"""s259 — общее: вселенная перпов, дата спота Binance, «без спота на момент», состав индекса (снимок s252).
Запуск скриптов — из /home/user/mc_data (python3 -I <repo>/research/s259/study/<скрипт>.py)."""
import json
import os
import pickle
import re

import numpy as np
import pandas as pd

DAY, H, BAR = 86400, 3600, 900
T0 = int(pd.Timestamp("2024-10-01", tz="UTC").timestamp())
T1 = int(pd.Timestamp("2026-10-19", tz="UTC").timestamp())
MID = int(pd.Timestamp("2025-10-01", tz="UTC").timestamp())          # граница половин (как s253)
SKIP = {"USDT", "USDC", "USDE", "USD1", "USDS", "DAI", "FDUSD", "TUSD", "USDP", "BUSD", "PYUSD", "RLUSD",
        "XAU", "XAG", "XPT", "XPD", "PAXG", "XAUT", "BTCDOM", "DEFI"}           # стейблкоины, металлы, индексы (BL_SKIP бота)
OLD_SPOT = {"RENDER": 1635724800}                                               # спот под прежним тикером (RNDR, s253)
OUT = "s259"
TMP = "/dev/shm/s259"                   # крупные промежуточные таблицы — в памяти (диск почти полон)
os.makedirs(TMP, exist_ok=True)


def base(fs):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs)
    return m.group(2) if m and not m.group(2)[0].isdigit() else fs


def load_k():
    return pickle.load(open(os.environ.get("MC_K", "s2/k2y.pkl"), "rb"))


def crypto_perps(K):
    """Криптоперпы USDT-M: без TradFi (акции, сырьё), индексов, стейблкоинов и металлов. Снятые (нет в exinfo) — крипта."""
    FX = {x["symbol"][:-4]: x for x in json.load(open("s252/exinfo.json"))["symbols"] if x["symbol"].endswith("USDT")}
    out = []
    for p in K:
        if base(p) in SKIP:
            continue
        if p in FX and not (FX[p]["contractType"] == "PERPETUAL" and FX[p].get("underlyingType") == "COIN"):
            continue
        out.append(p)
    return sorted(out)


def spot_start(perps):
    """Как s253: самая ранняя из первой дневной свечи спота (s252/spot_dates.json), первой часовой свечи спота с оборотом
    (s23/spot1h.pkl) и прежнего тикера. None — спота Binance не было."""
    SD = json.load(open("s252/spot_dates.json"))
    SP = pickle.load(open("s23/spot1h.pkl", "rb"))
    out = {}
    for p in perps:
        c = [SD.get(base(p)), SD.get(p)]
        for k in {p, base(p)}:
            a = SP.get(k)
            if a is not None and len(a) and (a[:, 1] > 0).any():
                c.append(float(a[a[:, 1] > 0, 0].min()))
        if p in OLD_SPOT:
            c.append(OLD_SPOT[p])
        c = [float(x) for x in c if x]
        out[p] = min(c) if c else None
    return out


def live(a):
    nz = np.flatnonzero(a["qv"] > 0)
    return (int(a["t"][nz[0]]), int(a["t"][nz[-1]])) if len(nz) else (None, None)


def snapshot():
    """Состав индекса перпов без спота (снимок 23.11.2026): перп → веса по типам площадок."""
    NS = json.load(open("s252/nospot.json"))
    out = {}
    for k, v in NS.items():
        w = {}
        for c in v["cons"]:
            e = c["exchange"]
            w[e] = w.get(e, 0.0) + float(c["weight"])
        dex = sum(x for e, x in w.items() if e not in CEX)
        ext = {e: x for e, x in w.items() if e in CEX and e not in ("binance_future", "binance_alpha")}
        out[k[:-4]] = dict(self=w.get("binance_future", 0.0), alpha=w.get("binance_alpha", 0.0), dex=dex,
                           ext=sum(ext.values()), ext_max=max(ext.values(), default=0.0), n=len(v["cons"]), w=w)
    return out


CEX = {"binance_future", "binance_alpha", "gateio", "mexc", "kucoin", "bitget", "bybit", "okex", "coinbase", "bitfinex",
       "htx", "huobi", "kraken", "upbit", "bithumb", "lbank", "bingx", "binance"}


def ct(x, t, week=7 * DAY):
    """Среднее и t по неделям (суммы отклонений по неделям, как s256)."""
    x = np.asarray(x, float); w = (np.asarray(t, np.int64) // week) * week; ok = np.isfinite(x); x, w = x[ok], w[ok]
    if len(x) < 5:
        return np.nan, np.nan, len(x)
    m = x.mean(); s = pd.Series(x - m).groupby(w).sum(); se = np.sqrt((s ** 2).sum()) / len(x)
    return m, (m / se if se > 0 else np.nan), len(x)
