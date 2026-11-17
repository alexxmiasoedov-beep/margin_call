"""s93 — часовые свечи пар к местной валюте Indodax (IDR), Bitkub (THB) и CoinDCX (INR) у монет с бессрочным фьючерсом
Binance (список фьючерсов — архив data.binance.vision), плюс курс USDT к местной валюте. 01.10.2024–20.10.2026, без ключей.
Результат — s93/<биржа>.pkl {монета: массив [начало часа, закрытие, объём в монете]}; кэш по паре — s93/c/<биржа>/,
прерванный сбор продолжается. Запуск из папки с данными: python3 <путь>/s93/fetch.py"""
import json
import os
import pickle
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np

T0, T1 = 1727740800, 1792540800                                   # 01.10.2024 — 20.10.2026
UA = {"User-Agent": "Mozilla/5.0 (research)"}
LIST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/klines/"
STABLE = {"USDT", "USDC", "FDUSD", "TUSD", "DAI", "BUSD", "USDE", "USD1", "PYUSD", "IDRT", "BIDR", "EUR", "XAUT", "PAXG"}


def get(url, tries=5):
    for k in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40).read())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return None
        except Exception:
            pass
        time.sleep(2 + 3 * k)
    return "ERR"


def um_symbols():
    syms, marker = [], ""
    while True:
        x = urllib.request.urlopen(urllib.request.Request(LIST + (f"&marker={marker}" if marker else ""), headers=UA), timeout=40).read().decode()
        p = re.findall(r"<Prefix>data/futures/um/monthly/klines/([^/<]+)/</Prefix>", x)
        syms += p
        if "<IsTruncated>true</IsTruncated>" not in x or not p:
            return set(syms)
        marker = f"data/futures/um/monthly/klines/{p[-1]}/"


def has_fut(b, um):
    return any(f"{p}{b}USDT" in um for p in ("", "1000", "1000000"))


def pairs(um):
    """Пары каждой биржи: {биржа: {монета: идентификатор пары}}; USDT — курс."""
    out = {"indodax": {}, "bitkub": {}, "coindcx": {}}
    for x in get("https://indodax.com/api/pairs") or []:
        if x.get("base_currency") == "idr":
            b = x["traded_currency"].upper()
            if b == "USDT" or (has_fut(b, um) and b not in STABLE):
                out["indodax"][b] = x["symbol"]
    for x in get("https://api.bitkub.com/api/v3/market/ticker") or []:
        s = x.get("symbol", "")
        if s.endswith("_THB"):
            b = s[:-4]
            if b == "USDT" or (has_fut(b, um) and b not in STABLE):
                out["bitkub"][b] = s
    for x in get("https://api.coindcx.com/exchange/v1/markets_details") or []:
        if x.get("base_currency_short_name") == "INR" and str(x.get("pair", "")).startswith("I-"):
            b = x["target_currency_short_name"].upper()
            if b == "USDT" or (has_fut(b, um) and b not in STABLE):
                out["coindcx"][b] = x["pair"]
    return out


def candles(ex, b, pid):
    """Все часовые свечи пары за T0–T1: {час: (закрытие, объём в монете)} или None при сбое."""
    path = f"s93/c/{ex}/{b}.pkl"
    if os.path.exists(path):
        return True
    rows = {}
    step = {"indodax": 25, "bitkub": 55, "coindcx": 40}[ex] * 86400
    for a in range(T0, T1, step):
        z = min(a + step, T1)
        if ex == "indodax":
            j = get(f"https://indodax.com/tradingview/history_v2?symbol={pid}&tf=60&from={a}&to={z}")
            if j == "ERR":
                return False
            for r in j or []:
                rows[int(r["Time"])] = (float(r["Close"]), float(r["Volume"]))
        elif ex == "bitkub":
            j = get(f"https://api.bitkub.com/tradingview/history?symbol={pid}&resolution=60&from={a}&to={z}")
            if j == "ERR":
                return False
            if isinstance(j, dict) and j.get("s") == "ok":
                for t, c, v in zip(j["t"], j["c"], j["v"]):
                    rows[int(t)] = (float(c), float(v))
        else:
            j = get(f"https://public.coindcx.com/market_data/candles?pair={pid}&interval=1h&startTime={a * 1000}&endTime={z * 1000}&limit=1000")
            if j == "ERR":
                return False
            for r in j or []:
                rows[int(r["time"]) // 1000] = (float(r["close"]), float(r["volume"]))
        time.sleep(0.3)
    t = np.array(sorted(k for k in rows if T0 <= k < T1), dtype=np.int64)
    res = np.column_stack([t, [rows[k][0] for k in t], [rows[k][1] for k in t]]) if len(t) else np.zeros((0, 3))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pickle.dump(res, open(path + ".tmp", "wb")); os.replace(path + ".tmp", path)
    return True


def main():
    um = um_symbols()
    P = pairs(um)
    print("пар с фьючерсом Binance: " + ", ".join(f"{ex} {len(v)}" for ex, v in P.items()), flush=True)
    pickle.dump(P, open("s93/pairs.pkl", "wb"))
    for rnd in range(3):
        bad = []
        with ThreadPoolExecutor(3) as p1, ThreadPoolExecutor(3) as p2, ThreadPoolExecutor(3) as p3:
            pool = {"indodax": p1, "bitkub": p2, "coindcx": p3}
            fs = [((ex, b), pool[ex].submit(candles, ex, b, pid)) for ex, d in P.items() for b, pid in d.items()]
            for i, (key, f) in enumerate(fs):
                if not f.result():
                    bad.append(key)
        print(f"проход {rnd + 1}: не скачано {len(bad)}", flush=True)
        if not bad:
            break
        time.sleep(60)
    for ex, d in P.items():
        out = {}
        for b in d:
            path = f"s93/c/{ex}/{b}.pkl"
            if os.path.exists(path):
                out[b] = pickle.load(open(path, "rb"))
        pickle.dump(out, open(f"s93/{ex}.pkl", "wb"))
        print(f"{ex}: {len(out)} пар, со свечами {sum(1 for v in out.values() if len(v))}", flush=True)
    print("готово", flush=True)


if __name__ == "__main__":
    sys.exit(main())
