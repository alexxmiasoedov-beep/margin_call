"""Данные по одной монете из открытого архива Binance (data.binance.vision), фьючерсы USDT-M:
лента сделок (aggTrades, по месяцам), открытый интерес и соотношения лонгов/шортов каждые 5 мин (metrics, по дням),
толщина стакана в пределах ±1…5% от цены каждые 30 с (bookDepth, по дням), фандинг и премия к индексу (по месяцам).
Каждый файл сверяется с контрольной суммой из архива (.CHECKSUM). Уже скачанные пропускаются.

Запуск из папки с данными: python3 s14/fetch.py GPS 2025-02-17 2026-10-31 ONE 2024-10-01 2026-10-31
Файлы — в s14raw/<МОНЕТА>/<вид>/."""
import datetime
import hashlib
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://data.binance.vision/data/futures/um"
MONTHLY = (("aggTrades", "aggTrades"), ("fundingRate", "fundingRate"), ("premiumIndexKlines/{s}/15m", "15m"))
DAILY = ("metrics", "bookDepth")


def jobs(coin, d0, d1):
    s = coin + "USDT"; out = []
    d = d0
    while d <= d1:
        for kind in DAILY:
            out.append((f"{BASE}/daily/{kind}/{s}/{s}-{kind}-{d:%Y-%m-%d}.zip", os.path.join("s14raw", coin, kind)))
        d += datetime.timedelta(days=1)
    m = d0.replace(day=1)
    while m <= d1:
        for path, tag in MONTHLY:
            kind = path.split("/")[0]
            sub = path.format(s=s) if "{s}" in path else f"{kind}/{s}"
            out.append((f"{BASE}/monthly/{sub}/{s}-{tag}-{m:%Y-%m}.zip", os.path.join("s14raw", coin, kind)))
        m = (m + datetime.timedelta(days=32)).replace(day=1)
    return out


def get(url, timeout=120):
    for i in range(4):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except OSError:
            pass
        time.sleep(2 ** (i + 1))
    raise OSError(f"не скачано: {url}")


def fetch(job):
    try:
        return _fetch(job)
    except OSError as e:
        print("сбой:", e, flush=True)                     # остальное качаем дальше; повторный запуск докачает
        return "сбой"


def _fetch(job):
    url, folder = job
    path = os.path.join(folder, url.rsplit("/", 1)[1])
    if os.path.exists(path) or os.path.exists(path + ".none"):
        return "есть"
    ck = get(url + ".CHECKSUM")
    if ck is None:
        open(path + ".none", "w").close()                 # в архиве нет (монеты ещё не было или день без данных)
        return "нет"
    data = get(url)
    if data is None or hashlib.sha256(data).hexdigest() != ck.decode().split()[0]:
        raise OSError(f"контрольная сумма не сошлась: {url}")
    with open(path + ".tmp", "wb") as f:
        f.write(data)
    os.replace(path + ".tmp", path)
    return "скачан"


if __name__ == "__main__":
    a = sys.argv[1:]; todo = []
    for coin, d0, d1 in zip(a[::3], a[1::3], a[2::3]):
        for job in jobs(coin, datetime.date.fromisoformat(d0), datetime.date.fromisoformat(d1)):
            os.makedirs(job[1], exist_ok=True); todo.append(job)
    t0 = time.time(); res = {}
    with ThreadPoolExecutor(8) as ex:
        for i, r in enumerate(ex.map(fetch, todo), 1):
            res[r] = res.get(r, 0) + 1
            if i % 200 == 0 or i == len(todo):
                print(f"{i}/{len(todo)} за {time.time() - t0:.0f} с: " + ", ".join(f"{k} {v}" for k, v in res.items()), flush=True)
