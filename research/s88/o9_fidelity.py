"""s88 — сверка правила бота ⏰ (scanner.open9_rule) с бэктестом: настоящая функция бота прогоняется по каждому дню
10.2024–10.2026 в 01:05 UTC, ответы Binance, Upbit и Bithumb подменяются историей (15-мин свечи s2/k2y.pkl, часовые свечи
s15/kr_candles_<биржа>.pkl). Входы бота сравниваются с событиями бэктеста (s88/trades.pkl: час открытия, рост ≥ 5%,
доля ≥ 20%). Отдельно — сколько событий бот пропустит, потому что сделка по монете ещё открыта (держится до 48 ч).
Запуск из папки с данными: python3 <путь>/s88/o9_fidelity.py"""
import os
import pickle
import sys
import tempfile
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
os.environ["POSITION_USDT"] = "1"
sys.path.insert(0, os.path.join(HERE, "..", "..", "bot"))
for p in ("s15", "s43"):
    sys.path.insert(0, os.path.join(HERE, "..", p))
import scanner, trader  # noqa: E402
from common import K, fut_of, live, trade  # noqa: E402
from oi_test import DAY, ct  # noqa: E402

CLOCK = [0]
time.time = lambda: CLOCK[0]
trader.funding_hourly = lambda sym: None
scanner.log = lambda *a, **k: None
KC = {ex: pickle.load(open(f"s15/kr_candles_{ex}.pkl", "rb")) for ex in ("upbit", "bithumb")}
FX = {ex: pd.Series(KC[ex]["USDT"]["c"].astype(float), index=KC[ex]["USDT"]["t"]) for ex in KC}
SYMS = [s for s in K if s != "BTC" or True]
LIVE = {s: live(s) for s in SYMS}
NOW = {"T": 0}


def coin_of(s):
    import re
    return re.sub(r"^(1000000|100000|10000|1000)", "", s)


def ticker24():
    T = NOW["T"]; out = []
    for s in SYMS:
        lo_t, hi_t = LIVE[s]
        if not lo_t <= T <= hi_t:
            continue
        a = K[s]; t = a["t"]
        i0, i1 = np.searchsorted(t, T - DAY), np.searchsorted(t, T + 300)
        if i1 - i0 < 8:
            continue
        out.append({"symbol": f"{s}USDT", "highPrice": str(float(a["h"][i0:i1].max())), "lowPrice": str(float(a["l"][i0:i1].min()))})
    return out


def kline_rows(s, T):
    a = K[s]; t = a["t"]
    i1 = np.searchsorted(t, T + 1)                               # свечи с открытием ≤ T (последняя — открытая в T)
    i0 = max(0, i1 - 7)
    return [[int(t[i]) * 1000, float(a["o"][i]), float(a["h"][i]), float(a["l"][i]), float(a["c"][i]), 0.0,
             (int(t[i]) + 900) * 1000 - 1, float(a["qv"][i])] for i in range(i0, i1)]


def http_json(url, timeout=30):
    T = NOW["T"]
    if "fapi.binance.com/fapi/v1/klines" in url:
        s = url.split("symbol=")[1].split("USDT")[0]
        return kline_rows(s, T) if s in K else None
    ex = "upbit" if "upbit" in url else "bithumb"
    coin = url.split("market=")[1].split("&")[0][4:]
    H = T - 3600
    if coin == "USDT":
        r = FX[ex].reindex(np.union1d(FX[ex].index, [H])).ffill().bfill().get(H)
        return [{"trade_price": float(r)}]
    x = KC[ex].get(coin)
    if x is None:
        return []
    i = np.searchsorted(x["t"], H)
    v = float(x["v"][i]) if i < len(x["t"]) and x["t"][i] == H else 0.0
    return [{"candle_date_time_utc": datetime.fromtimestamp(H + q * 900, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
             "candle_acc_trade_price": v / 4} for q in range(4)]


def kr_list():
    H = NOW["T"] - 3600
    return {ex: {c for c, x in KC[ex].items() if c != "USDT" and len(x["t"]) and x["t"][0] <= H <= x["t"][-1] + 86400}
            for ex in KC}


scanner.http_json = http_json
scanner.ticker24 = ticker24
scanner._kr_list = kr_list
trader.contract = lambda sym: ({"symbol": sym, "onboard": LIVE[sym.replace("USDT", "")][0]}
                               if sym.replace("USDT", "") in LIVE else None)


def main():
    X = pd.read_pickle("s88/trades.pkl")
    B = X[X.open9 & (X.r1 >= 0.05) & (X.share >= 0.20)]
    days = sorted({(int(t) - 3600) // DAY * DAY for t in X.t})
    d0, d1 = min(days), max(days)
    got = []
    for D in range(d0, d1 + DAY, DAY):
        T = D + 3600
        NOW["T"] = T; CLOCK[0] = T + 300
        trader._contracts = {f"{s}USDT": {} for s in SYMS if LIVE[s][0] <= T <= LIVE[s][1]}
        trader.mark_price = lambda sym, T=T: float(K[sym]["c"][np.searchsorted(K[sym]["t"], T - 900)])
        state = {}
        scanner.open9_rule(state)
        for t in state.get("virtual_O9", {}).get("trades", []):
            got.append((t["sym"], T))
    G = pd.DataFrame(got, columns=["s", "t"])
    bk = set(zip(B.s, B.t)); gk = set(zip(G.s, G.t))
    print(f"Бэктест: {len(bk)} событий; бот: {len(gk)} входов; совпало {len(bk & gk)}; только в бэктесте {len(bk - gk)};"
          f" только у бота {len(gk - bk)}")
    for s, t in sorted(bk - gk)[:8]:
        print("  нет у бота:", s, datetime.fromtimestamp(t, timezone.utc).strftime("%d.%m.%Y"))
    for s, t in sorted(gk - bk)[:8]:
        print("  лишний у бота:", s, datetime.fromtimestamp(t, timezone.utc).strftime("%d.%m.%Y"))
    # сделка по монете ещё открыта (держится до 48 ч) — бот второй вход не откроет
    Bs = B.sort_values("t"); busy, skip = {}, []
    for s, t in zip(Bs.s, Bs.t):
        j = int(np.searchsorted(K[s]["t"], t - 900))
        x = trade(s, j, tp=0.10, sl=0.25, hold_h=48)
        if t < busy.get(s, 0):
            skip.append((s, t)); continue
        busy[s] = t + (x["bars"] * 900 if x else 48 * 3600)
    kept = B[~B.set_index(["s", "t"]).index.isin(skip)]
    m1, t1, n1 = ct(B.S_10_25, B.t); m2, t2, n2 = ct(kept.S_10_25, kept.t)
    print(f"Пропуск из-за открытой сделки по той же монете: {len(skip)}; доход всех событий {m1:+.2%} (t {t1:.1f}, {n1}),"
          f" без пропущенных {m2:+.2%} (t {t2:.1f}, {n2})")


if __name__ == "__main__":
    main()
