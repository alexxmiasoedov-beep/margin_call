"""s278 — часовые свечи спота (пары к USDT) бирж OKX, Bitget, KuCoin, Gate, HTX, MEXC у монет с перпом Binance.
Только данные: оборот за час в $ (котировка USDT), открытие и закрытие. Без ключей, User-Agent research-script/1.0,
не больше ~4–5 запросов в секунду к хосту, при 429 и ошибках — пауза.

Периоды: P1 — 01.10.2024–20.11.2026 (монеты перпов s224/k_d), P0 — 01.10.2022–01.10.2024 (монеты перпов s117/k_oos).
История: OKX, Bitget, KuCoin — обе; Gate — только ~10000 последних часов (≈ 14 мес.); HTX — 2000 последних часов;
MEXC — 1000 последних часов (только «сейчас»). Пары — текущие списки бирж (снятые пары не попадают).

Результат: /dev/shm/s278/raw/<биржа>/<период>/<монета>.npz (t — начало часа, с; o, c, qv). Прерванный сбор продолжается.
Запуск: python3 -I fetch_venues.py <биржа> [P1|P0] [byvol] — byvol: сначала пары с наибольшим оборотом за 24 ч сейчас
(один сборщик на биржу; в s278 Bitget остановлен на 266 парах из 364)."""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import numpy as np

UA = {"User-Agent": "research-script/1.0"}
ROOT = "/dev/shm/s278"
PER = {"P1": (1727740800, 1795219200), "P0": (1664582400, 1727740800)}
H = 3600
PAUSE = {"okx": 0.26, "bitget": 0.21, "kucoin": 0.26, "gate": 0.26, "htx": 0.3, "mexc": 0.3}


def get(url, tries=6):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(10 + 10 * k)
                continue
            if e.code in (400, 404):
                try:
                    return json.loads(e.read().decode())
                except Exception:
                    return {}
        except Exception:
            pass
        time.sleep(2 + 3 * k)
    return None


def okx(coin, t0, t1):
    rows, after = {}, t1 * 1000
    while True:
        x = get(f"https://www.okx.com/api/v5/market/history-candles?instId={coin}-USDT&bar=1H&after={after}&limit=300")
        time.sleep(PAUSE["okx"])
        if x is None:
            return None
        if str(x.get("code")) in ("50011", "50061"):           # лимит запросов — пауза и повтор
            time.sleep(5)
            continue
        d = x.get("data") or []
        if not d:
            break
        for r in d:
            ts = int(r[0]) // 1000
            if t0 <= ts < t1:
                rows[ts] = (float(r[1]), float(r[4]), float(r[7]))
        mn = min(int(r[0]) for r in d)
        if mn // 1000 <= t0 or len(d) < 300:
            break
        after = mn
    return rows


def bitget(coin, t0, t1):
    rows, end = {}, t1 * 1000
    while True:
        x = get(f"https://api.bitget.com/api/v2/spot/market/history-candles?symbol={coin}USDT&granularity=1h&endTime={end}&limit=200")
        time.sleep(PAUSE["bitget"])
        if x is None:
            return None
        if str(x.get("code")) == "429":
            time.sleep(5)
            continue
        d = x.get("data") or []
        if not d:
            break
        for r in d:
            ts = int(r[0]) // 1000
            if t0 <= ts < t1:
                rows[ts] = (float(r[1]), float(r[4]), float(r[6]))
        mn = min(int(r[0]) for r in d)
        if mn // 1000 <= t0 or len(d) < 200 or mn >= end:
            break
        end = mn
    return rows


def kucoin(coin, t0, t1):
    rows, end = {}, t1
    while end > t0:
        a = max(t0, end - 1500 * H)
        x = get(f"https://api.kucoin.com/api/v1/market/candles?type=1hour&symbol={coin}-USDT&startAt={a}&endAt={end}")
        time.sleep(PAUSE["kucoin"])
        if x is None:
            return None
        if str(x.get("code")) == "429000":
            time.sleep(10)
            continue
        for r in x.get("data") or []:
            ts = int(r[0])
            if t0 <= ts < t1:
                rows[ts] = (float(r[1]), float(r[2]), float(r[6]))
        end = a
    return rows


def gate(coin, t0, t1):
    rows = {}
    now = int(time.time()) // H * H
    lo = max(t0, now - 9990 * H)
    a = lo
    while a < t1:
        z = min(a + 999 * H, t1 - H)
        if z < a:
            break
        x = get(f"https://api.gateio.ws/api/v4/spot/candlesticks?currency_pair={coin}_USDT&interval=1h&from={a}&to={z}")
        time.sleep(PAUSE["gate"])
        if x is None:
            return None
        if isinstance(x, list):
            for r in x:
                ts = int(r[0])
                if t0 <= ts < t1:
                    rows[ts] = (float(r[5]), float(r[2]), float(r[1]))
        a = z + H
    return rows


def htx(coin, t0, t1):
    x = get(f"https://api.huobi.pro/market/history/kline?symbol={coin.lower()}usdt&period=60min&size=2000")
    time.sleep(PAUSE["htx"])
    if x is None:
        return None
    rows = {}
    for r in x.get("data") or []:
        ts = int(r["id"])
        if t0 <= ts < t1:
            rows[ts] = (float(r["open"]), float(r["close"]), float(r["vol"]))
    return rows


def mexc(coin, t0, t1):
    x = get(f"https://api.mexc.com/api/v3/klines?symbol={coin}USDT&interval=60m&limit=1000")
    time.sleep(PAUSE["mexc"])
    if x is None:
        return None
    rows = {}
    if isinstance(x, list):
        for r in x:
            ts = int(r[0]) // 1000
            if t0 <= ts < t1:
                rows[ts] = (float(r[1]), float(r[4]), float(r[7]))
    return rows


FN = {"okx": okx, "bitget": bitget, "kucoin": kucoin, "gate": gate, "htx": htx, "mexc": mexc}


def volumes(ven):
    """Оборот пар к USDT за 24 ч сейчас (одним запросом тикеров): монета → $. Нужен только для порядка сбора."""
    out = {}
    try:
        if ven == "okx":
            for x in get("https://www.okx.com/api/v5/market/tickers?instType=SPOT")["data"]:
                if x["instId"].endswith("-USDT"):
                    out[x["instId"][:-5]] = float(x.get("volCcy24h") or 0)
        elif ven == "bitget":
            for x in get("https://api.bitget.com/api/v2/spot/market/tickers")["data"]:
                if x["symbol"].endswith("USDT"):
                    out[x["symbol"][:-4]] = float(x.get("usdtVolume") or 0)
        elif ven == "kucoin":
            for x in get("https://api.kucoin.com/api/v1/market/allTickers")["data"]["ticker"]:
                if x["symbol"].endswith("-USDT"):
                    out[x["symbol"][:-5]] = float(x.get("volValue") or 0)
        elif ven == "gate":
            for x in get("https://api.gateio.ws/api/v4/spot/tickers"):
                if x["currency_pair"].endswith("_USDT"):
                    out[x["currency_pair"][:-5]] = float(x.get("quote_volume") or 0)
    except Exception:
        pass
    return out


def main():
    ven = sys.argv[1]
    pers = [p for p in sys.argv[2:] if p in PER] or (["P1", "P0"] if ven in ("okx", "bitget", "kucoin") else ["P1"])
    VP = json.load(open(f"{ROOT}/venue_pairs.json"))[ven]
    log = open(f"{ROOT}/log_{ven}.txt", "a")
    for per in pers:
        t0, t1 = PER[per]
        bases = set(json.load(open(f"{ROOT}/perps_{'d' if per == 'P1' else 'oos'}.json"))["base"].values())
        coins = [c for c in VP if c in bases]
        if "byvol" in sys.argv:                                # сначала пары с наибольшим оборотом за 24 ч сейчас
            vol = volumes(ven)
            coins.sort(key=lambda c: -vol.get(c, 0.0))
        out = f"{ROOT}/raw/{ven}/{per}"
        os.makedirs(out, exist_ok=True)
        t_start, done, bad = time.time(), 0, []
        for c in coins:
            f = f"{out}/{c}.npz"
            if os.path.exists(f):
                continue
            rows = FN[ven](c, t0, t1)
            if rows is None:
                bad.append(c)
                continue
            t = np.array(sorted(rows), dtype=np.int64)
            v = np.array([rows[k] for k in t], dtype=np.float64).reshape(-1, 3)
            np.savez_compressed(f + ".tmp.npz", t=t, o=v[:, 0].astype(np.float32), c=v[:, 1].astype(np.float32),
                                qv=v[:, 2].astype(np.float32))
            os.replace(f + ".tmp.npz", f)
            done += 1
            if done % 20 == 0:
                print(f"{ven} {per}: {done}/{len(coins)}, {time.time() - t_start:.0f} с", file=log, flush=True)
        print(f"{ven} {per}: готово {done} из {len(coins)}, сбой {len(bad)}: {bad[:20]}", file=log, flush=True)


if __name__ == "__main__":
    main()
