"""Листинги к воне на Upbit и Bithumb с 01.10.2024: время начала торгов по первой минутной свече рынка.
Берутся рынки из текущих списков бирж (снятые с торгов к сегодняшнему дню сюда не попадают — для шорта это
осторожная оценка: такие монеты обычно падали). Результат — s15/kr_listings.pkl: [{ex, market, base, t}].

Запуск из папки с данными: python3 s15/kr_listings.py"""
import datetime
import json
import os
import pickle
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UTC = datetime.timezone.utc
SINCE = datetime.datetime(2024, 10, 1, tzinfo=UTC)
API = {"upbit": "https://api.upbit.com", "bithumb": "https://api.bithumb.com"}


def get(url):
    for i in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "margin-call research"}), timeout=20) as r:
                x = json.loads(r.read().decode())
            if isinstance(x, list):
                return x
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):                            # неверный запрос или нет рынка — повтор не поможет
                return None
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))                               # лимит запросов или сбой — пауза и повтор
    return None


def iso(dt, ex):
    """Граница to: Upbit ждёт UTC с «Z», Bithumb — время Сеула без зоны (с «Z» отвечает 400)."""
    if ex == "bithumb":
        return (dt.astimezone(UTC) + datetime.timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:%S")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc(x):
    return datetime.datetime.fromisoformat(x["candle_date_time_utc"]).replace(tzinfo=UTC)


def first_minute(ex, market):
    """Первая минута торгов рынка, если он открыт после SINCE; иначе None."""
    base = API[ex]
    old = get(f"{base}/v1/candles/days?market={market}&count=1&to={iso(SINCE, ex)}"); time.sleep(0.12)
    if old:                                                    # свечи до SINCE есть — рынок старый
        return None
    to, first_day = datetime.datetime.now(UTC), None
    for _ in range(6):                                         # дневные свечи назад до первой
        d = get(f"{base}/v1/candles/days?market={market}&count=200&to={iso(to, ex)}"); time.sleep(0.12)
        if not d:
            break
        first_day = min(utc(x) for x in d)
        if len(d) < 200:
            break
        to = first_day
    if not first_day:
        return None
    to, first = first_day + datetime.timedelta(days=1), None
    for _ in range(10):                                        # минутные свечи первого дня назад до первой
        c = get(f"{base}/v1/candles/minutes/1?market={market}&count=200&to={iso(to, ex)}"); time.sleep(0.12)
        if not c:
            break
        first = min(utc(x) for x in c)
        if len(c) < 200:
            break
        to = first
    return first.timestamp() if first else None


def exchange(ex):
    """Все рынки к воне биржи — 4 потока (лимит свечей Upbit — 10 запросов в секунду с IP). Кэш биржи — s15/kr_listings_<биржа>.pkl."""
    path = f"s15/kr_listings_{ex}.pkl"
    if os.path.exists(path):
        return pickle.load(open(path, "rb"))
    mk = [m["market"] for m in get(f"{API[ex]}/v1/market/all") or [] if m["market"].startswith("KRW-")]
    with ThreadPoolExecutor(4) as pool:
        ts = list(pool.map(lambda m: first_minute(ex, m), mk))
    res = [dict(ex=ex, market=m, base=m.split("-", 1)[1], t=t) for m, t in zip(mk, ts) if t]
    print(f"{ex}: рынков к воне {len(mk)}, открыты после {SINCE:%d.%m.%Y}: {len(res)}", flush=True)
    pickle.dump(res, open(path, "wb"))
    return res


if __name__ == "__main__":
    with ThreadPoolExecutor(2) as pool:
        out = [x for r in pool.map(exchange, ("upbit", "bithumb")) for x in r]
    os.makedirs("s15", exist_ok=True)
    pickle.dump(out, open("s15/kr_listings.pkl", "wb"))
    for x in sorted(out, key=lambda x: x["t"])[-10:]:
        print(" ", x["ex"], x["market"], datetime.datetime.fromtimestamp(x["t"], UTC).strftime("%d.%m.%Y %H:%M UTC"))
