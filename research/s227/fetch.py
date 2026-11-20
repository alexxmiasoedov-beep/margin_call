"""s227 — сбор данных по одной монете CYBER (фьючерс CYBERUSDT, Binance), бесплатно и без ключей. Итог — /home/user/mc_data/s227/.

Этапы (каждый докачивает только недостающее):
- metrics — метрики позиций data.binance.vision за все сутки с 21.08.2023: строки в начале часа (OI, OI $, лонг/шорт
  топ-трейдеров по счетам и по позициям, всех счетов, отношение агрессивных объёмов) → metrics/<день>.npy;
- prem — часовые свечи премии к индексу (premiumIndexKlines) → prem.npy [начало часа, o, h, l, c];
- spot — часовые свечи спота CYBERUSDT → spot.npy [начало часа, o, h, l, c, объём, оборот $, сделок, покупки, покупки $];
- tryk — часовые свечи CYBERTRY за 11.2026 (остальное есть в s15/try) → try_tail.npy;
- kr — часовые свечи Bithumb KRW-CYBER и KRW-USDT до 28.09.2024 и хвосты Upbit/Bithumb после 17.10.2026 →
  kr_<биржа>_<рынок>_<год>.npy;
- cmc — монеты в обращении и капитализация CMC за 15.08.2023–01.08.2024 → cmc_old.json.
Запуск из /home/user/mc_data: python3 <repo>/research/s227/fetch.py [этап …]"""
import datetime
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np

UA = {"User-Agent": "research-script/1.0"}
UTC = datetime.timezone.utc
OUT = "s227"
DAY0, DAY1 = datetime.date(2023, 8, 21), datetime.date(2026, 11, 19)
DV = "https://data.binance.vision/data"


def get(url, tries=4, timeout=60):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(3 * (k + 1))
        except Exception:
            time.sleep(3 * (k + 1))
    raise RuntimeError(f"сбой сети: {url}")


def days(a=DAY0, b=DAY1):
    d = a
    while d <= b:
        yield d
        d += datetime.timedelta(days=1)


def months(a=DAY0, b=DAY1):
    y, m = a.year, a.month
    while (y, m) <= (b.year, b.month):
        yield f"{y}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def metrics():
    os.makedirs(f"{OUT}/metrics", exist_ok=True)

    def one(d):
        p = f"{OUT}/metrics/{d}.npy"
        if os.path.exists(p):
            return 0
        raw = get(f"{DV}/futures/um/daily/metrics/CYBERUSDT/CYBERUSDT-metrics-{d}.zip")
        rows = []
        if raw:
            z = zipfile.ZipFile(io.BytesIO(raw))
            for ln in z.read(z.namelist()[0]).decode().splitlines()[1:]:
                q = ln.split(",")
                if len(q) >= 8 and q[0].endswith(":00:00"):
                    t = datetime.datetime.strptime(q[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp()
                    rows.append([t] + [float(x.strip('"')) if x.strip('"') else np.nan for x in q[2:8]])
        np.save(p, np.array(rows) if rows else np.zeros((0, 7)))
        return 1
    with ThreadPoolExecutor(8) as ex:
        n = sum(ex.map(one, list(days())))
    print("метрики: докачано суток", n, flush=True)


def klines_zip(raw, ncol):
    z = zipfile.ZipFile(io.BytesIO(raw))
    out = []
    for ln in z.read(z.namelist()[0]).decode().splitlines():
        q = ln.split(",")
        if not q or not q[0].strip().isdigit():
            continue
        t = int(q[0]); t = t // 1000 if t < 10 ** 13 else t // 1_000_000      # спот с 2025 г. — микросекунды
        out.append([t] + [float(x) for x in q[1:ncol]])
    return out


def kl_series(kind, sym, interval, ncol, path):
    rows = []
    for m in months():
        raw = get(f"{DV}/{kind}/monthly/klines/{sym}/{interval}/{sym}-{interval}-{m}.zip") if kind == "spot" else \
            get(f"{DV}/{kind}/monthly/premiumIndexKlines/{sym}/{interval}/{sym}-{interval}-{m}.zip")
        if raw is None:                                         # текущий месяц — по суткам
            for d in days(max(DAY0, datetime.date(int(m[:4]), int(m[5:]), 1)), DAY1):
                if d.strftime("%Y-%m") != m:
                    continue
                r2 = get(f"{DV}/{kind}/daily/klines/{sym}/{interval}/{sym}-{interval}-{d}.zip") if kind == "spot" else \
                    get(f"{DV}/{kind}/daily/premiumIndexKlines/{sym}/{interval}/{sym}-{interval}-{d}.zip")
                if r2:
                    rows += klines_zip(r2, ncol)
            continue
        rows += klines_zip(raw, ncol)
    a = np.array(sorted({r[0]: r for r in rows}.values())) if rows else np.zeros((0, ncol))
    np.save(path, a)
    print(path, a.shape, (datetime.datetime.fromtimestamp(a[0, 0], UTC), datetime.datetime.fromtimestamp(a[-1, 0], UTC)) if len(a) else "",
          flush=True)


def kr():
    """Bithumb и Upbit: публичные свечи (как research/s15/kr_listings.API) — по 200 часов назад от to."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "s15"))
    for ex, mk, a, b in (("bithumb", "KRW-CYBER", datetime.datetime(2023, 8, 14, tzinfo=UTC), datetime.datetime(2024, 9, 28, 8, tzinfo=UTC)),
                         ("bithumb", "KRW-USDT", datetime.datetime(2023, 8, 14, tzinfo=UTC), datetime.datetime(2024, 9, 28, 8, tzinfo=UTC)),
                         ("bithumb", "KRW-CYBER", datetime.datetime(2026, 10, 17, 23, tzinfo=UTC), datetime.datetime(2026, 11, 20, tzinfo=UTC)),
                         ("bithumb", "KRW-USDT", datetime.datetime(2026, 10, 17, 23, tzinfo=UTC), datetime.datetime(2026, 11, 20, tzinfo=UTC)),
                         ("upbit", "KRW-CYBER", datetime.datetime(2026, 10, 17, 23, tzinfo=UTC), datetime.datetime(2026, 11, 20, tzinfo=UTC)),
                         ("upbit", "KRW-USDT", datetime.datetime(2026, 10, 17, 23, tzinfo=UTC), datetime.datetime(2026, 11, 20, tzinfo=UTC))):
        host = "https://api.bithumb.com" if ex == "bithumb" else "https://api.upbit.com"
        rows, to = {}, b
        while to > a:
            tt = ((to + datetime.timedelta(hours=9)).strftime('%Y-%m-%dT%H:%M:%S') if ex == "bithumb"   # Bithumb — время Сеула без зоны
                  else to.strftime('%Y-%m-%dT%H:%M:%SZ'))
            u = f"{host}/v1/candles/minutes/60?market={mk}&count=200&to={tt}"
            try:
                j = json.loads(get(u) or b"[]")
            except Exception as e:
                print(ex, "сбой", e, flush=True); break
            if not isinstance(j, list) or not j:
                break
            for x in j:
                t = int(datetime.datetime.fromisoformat(x["candle_date_time_utc"]).replace(tzinfo=UTC).timestamp())
                rows[t] = [t, float(x["trade_price"]), float(x["candle_acc_trade_price"])]
            to = datetime.datetime.fromtimestamp(min(rows), UTC)
            time.sleep(0.15 if ex == "upbit" else 0.05)
        arr = np.array([rows[t] for t in sorted(rows) if a.timestamp() <= t < b.timestamp()]) if rows else np.zeros((0, 3))
        p = f"{OUT}/kr_{ex}_{mk[4:]}_{a.year}.npy"
        np.save(p, arr)
        print(p, arr.shape, flush=True)


def cmc():
    a = int(datetime.datetime(2023, 8, 15, tzinfo=UTC).timestamp()); b = int(datetime.datetime(2024, 8, 2, tzinfo=UTC).timestamp())
    out = []
    for s, e in ((a, a + 200 * 86400), (a + 200 * 86400, b)):
        u = (f"https://api.coinmarketcap.com/data-api/v3/cryptocurrency/historical?id=24781&convertId=2781"
             f"&timeStart={s}&timeEnd={min(e, b)}&interval=1d")
        j = json.loads(get(u) or b"{}")
        for q in ((j.get("data") or {}).get("quotes") or []):
            qq = q.get("quote") or {}
            out.append([q.get("timeClose", "")[:10], qq.get("close"), qq.get("volume"), qq.get("marketCap"),
                        qq.get("circulatingSupply")])
        time.sleep(2)
    json.dump(out, open(f"{OUT}/cmc_old.json", "w"))
    print("CMC старые дни:", len(out), out[:1], out[-1:], flush=True)


def tryk():
    rows = []
    for d in days(datetime.date(2026, 11, 1), DAY1):
        raw = get(f"{DV}/spot/daily/klines/CYBERTRY/1h/CYBERTRY-1h-{d}.zip")
        if raw:
            rows += klines_zip(raw, 11)
    a = np.array(rows) if rows else np.zeros((0, 11)); np.save(f"{OUT}/try_tail.npy", a); print("лира хвост", a.shape, flush=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    st = sys.argv[1:] or ["metrics", "prem", "spot", "tryk", "kr", "cmc"]
    if "metrics" in st:
        metrics()
    if "prem" in st:
        kl_series("futures/um", "CYBERUSDT", "1h", 5, f"{OUT}/prem.npy")
    if "spot" in st:
        kl_series("spot", "CYBERUSDT", "1h", 11, f"{OUT}/spot.npy")
    if "tryk" in st:
        tryk()
    if "kr" in st:
        kr()
    if "cmc" in st:
        cmc()
