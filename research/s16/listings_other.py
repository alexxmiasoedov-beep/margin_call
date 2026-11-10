"""Листинги на Coinone (к воне) и Coinbase (к доллару) с 01.10.2024 — время первой свечи нового рынка: есть ли у них тот же
эффект, что у Upbit/Bithumb (research/s15, журнал 🇰🇷🆕). Рынки — из текущих списков бирж (снятые к сегодняшнему дню не
попадают — для шорта это осторожная оценка). Результат — s16/listings_other.pkl: [{ex, market, base, t}].

Запуск из папки с данными: python3 s16/listings_other.py"""
import datetime
import json
import os
import pickle
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UTC = datetime.timezone.utc
SINCE = datetime.datetime(2024, 10, 1, tzinfo=UTC).timestamp()
NOW = time.time()
DAY = 86400
STABLE = {"USDC", "USDT", "DAI", "PYUSD", "EURC", "GUSD", "USDS", "USDE", "USD1", "RLUSD", "FDUSD", "TUSD", "PAX", "PAXG",
          "WBTC", "CBBTC", "CBETH", "WETH", "XAUT"}


def get(url):
    for i in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "margin-call research"}), timeout=20) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):                         # неверный запрос или нет рынка — повтор не поможет
                return None
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))                            # лимит запросов или сбой — пауза и повтор
    return None


# ---------------------------------------------------------------- Coinone: /public/v2/chart, до 500 свечей, timestamp — конец окна
def coinone_chart(coin, interval, end_ms=None):
    url = f"https://api.coinone.co.kr/public/v2/chart/KRW/{coin}?interval={interval}&size=500" + (f"&timestamp={end_ms}" if end_ms else "")
    d = get(url)
    if not isinstance(d, dict) or d.get("result") != "success":
        return None, True
    return d.get("chart") or [], bool(d.get("is_last"))


def coinone_first(coin):
    end, first_day = None, None
    for _ in range(6):                                       # дневные свечи назад до первой
        ch, last = coinone_chart(coin, "1d", end); time.sleep(0.1)
        if ch is None:
            return None
        if not ch:
            break
        first_day = min(int(x["timestamp"]) for x in ch) / 1000
        if first_day < SINCE:
            return None                                      # рынок старый
        if last:
            break
        end = int(first_day * 1000) - 1
    if first_day is None:
        return None
    end, first = int((first_day + DAY) * 1000), None
    for _ in range(4):                                       # минутные свечи первого дня — первая с объёмом
        ch, last = coinone_chart(coin, "1m", end); time.sleep(0.1)
        if not ch:
            break
        live = [int(x["timestamp"]) / 1000 for x in ch if float(x.get("target_volume") or 0) > 0]
        if live:
            first = min(live)
        if last or min(int(x["timestamp"]) for x in ch) / 1000 < first_day:
            break
        end = min(int(x["timestamp"]) for x in ch) - 1
    return first or first_day


def coinone():
    d = get("https://api.coinone.co.kr/public/v2/markets/KRW")
    coins = [m["target_currency"] for m in (d or {}).get("markets", []) if m.get("target_currency") not in STABLE]
    with ThreadPoolExecutor(4) as pool:
        ts = list(pool.map(coinone_first, coins))
    res = [dict(ex="coinone", market=f"KRW-{c}", base=c, t=t) for c, t in zip(coins, ts) if t]
    print(f"coinone: рынков к воне {len(coins)}, открыты после 01.10.2024: {len(res)}", flush=True)
    return res


# ---------------------------------------------------------------- Coinbase: /products/{id}/candles, до 300 свечей за запрос
def cb_candles(pid, gran, start, end):
    s = datetime.datetime.fromtimestamp(start, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    e = datetime.datetime.fromtimestamp(end, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    d = get(f"https://api.exchange.coinbase.com/products/{pid}/candles?granularity={gran}&start={s}&end={e}")
    return d if isinstance(d, list) else None


def coinbase_first(pid):
    old = cb_candles(pid, DAY, SINCE - 30 * DAY, SINCE); time.sleep(0.15)
    if old is None or old:
        return None                                          # сбой или свечи до 01.10.2024 — рынок старый
    first_day, t = None, SINCE
    while t < NOW and first_day is None:                     # окна по 300 суток вперёд до первой свечи
        d = cb_candles(pid, DAY, t, min(t + 299 * DAY, NOW)); time.sleep(0.15)
        if d is None:
            return None
        if d:
            first_day = min(x[0] for x in d)
        t += 299 * DAY
    if first_day is None:
        return None
    first = None
    for k in range(5):                                       # минутные свечи первого дня, окна по 300 минут
        a = first_day + k * 300 * 60
        d = cb_candles(pid, 60, a, a + 299 * 60); time.sleep(0.15)
        if d:
            first = min(x[0] for x in d)
            break
    return float(first or first_day)


def coinbase():
    d = get("https://api.exchange.coinbase.com/products") or []
    prods = [p for p in d if p.get("quote_currency") in ("USD", "USDC", "USDT") and p.get("base_currency") not in STABLE
             and not p.get("fx_stablecoin")]
    with ThreadPoolExecutor(6) as pool:
        ts = list(pool.map(lambda p: coinbase_first(p["id"]), prods))
    best = {}
    for p, t in zip(prods, ts):                              # пары к USD и USDC — один листинг, берём самый ранний
        if t and (p["base_currency"] not in best or t < best[p["base_currency"]]["t"]):
            best[p["base_currency"]] = dict(ex="coinbase", market=p["id"], base=p["base_currency"], t=t)
    res = sorted(best.values(), key=lambda x: x["t"])
    print(f"coinbase: продуктов к USD/USDC/USDT {len(prods)}, монет с листингом после 01.10.2024: {len(res)}", flush=True)
    return res


if __name__ == "__main__":
    with ThreadPoolExecutor(2) as pool:
        out = [x for r in pool.map(lambda f: f(), (coinone, coinbase)) for x in r]
    os.makedirs("s16", exist_ok=True)
    pickle.dump(out, open("s16/listings_other.pkl", "wb"))
    for x in sorted(out, key=lambda x: x["t"])[-8:]:
        print(" ", x["ex"], x["market"], datetime.datetime.fromtimestamp(x["t"], UTC).strftime("%d.%m.%Y %H:%M UTC"))
