"""s42: данные data.binance.vision — индекс волатильности BVOL (BTC) по часам и часовые свечи квартальных
фьючерсов USDT-M BTC и ETH вместе с бессрочными. Запуск из папки данных: python3 <repo>/research/s42/fetch.py
Результат: s42/bvol.pkl (час → значение BVOL на начало часа), s42/q1h.pkl (символ → часовые свечи)."""
import concurrent.futures as cf
import datetime as dt
import io
import os
import pickle
import sys
import time
import urllib.error
import urllib.request
import zipfile

import numpy as np

BASE = "https://data.binance.vision/"
OUT = "s42"
BV_FROM, BV_TO = dt.date(2024, 6, 1), dt.date(2026, 10, 19)
QUARTERS = ["240628", "240927", "241227", "250328", "250627", "250926", "251226", "260327", "260626", "260925",
            "261225", "270326"]


def get(url, tries=5):
    for k in range(tries):
        try:
            return urllib.request.urlopen(url, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            time.sleep(2 * (k + 1))
        except Exception:
            time.sleep(2 * (k + 1))
    raise RuntimeError("не скачалось: " + url)


def bvol_day(sym, day):
    """Значение индекса на начало каждого часа дня: первая строка с calc_time ≥ начала часа (в пределах 5 мин)."""
    d = day.isoformat()
    raw = get(f"{BASE}data/option/daily/BVOLIndex/{sym}/{sym}-BVOLIndex-{d}.zip")
    if raw is None:
        return d, None
    z = zipfile.ZipFile(io.BytesIO(raw))
    txt = z.read(z.namelist()[0]).decode().splitlines()
    if txt and not txt[0][:1].isdigit():
        txt = txt[1:]
    t = np.array([int(r.split(",", 1)[0]) for r in txt], dtype=np.int64)
    v = np.array([float(r.rsplit(",", 1)[1]) for r in txt])
    o = np.argsort(t, kind="stable"); t, v = t[o], v[o]
    if t.size and t[0] > 1e14:                                 # микросекунды
        t //= 1000
    h0 = int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp()) * 1000
    hrs = h0 + np.arange(24) * 3600_000
    i = np.searchsorted(t, hrs)
    ok = (i < t.size) & (t[np.minimum(i, t.size - 1)] - hrs < 300_000)
    return d, {int(h // 1000): float(v[j]) for h, j, g in zip(hrs, i, ok) if g}


def klines_month(sym, ym):
    raw = get(f"{BASE}data/futures/um/monthly/klines/{sym}/1h/{sym}-1h-{ym}.zip")
    if raw is None:
        return sym, ym, None
    z = zipfile.ZipFile(io.BytesIO(raw))
    rows = [r.split(",") for r in z.read(z.namelist()[0]).decode().splitlines()]
    rows = [r for r in rows if r[0][:1].isdigit()]
    a = np.array([[int(r[0]) // 1000, float(r[4]), float(r[7])] for r in rows])   # открытие (с), закрытие, оборот $
    return sym, ym, a


def months(a, b):
    y, m = a.year, a.month
    while (y, m) <= (b.year, b.month):
        yield f"{y:04d}-{m:02d}"
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


def main():
    os.makedirs(OUT, exist_ok=True)
    what = sys.argv[1:] or ["bvol", "q"]
    if "q" in what:
        syms = ["BTCUSDT", "ETHUSDT"] + [f"{b}USDT_{q}" for b in ("BTC", "ETH") for q in QUARTERS]
        jobs = [(s, ym) for s in syms for ym in months(dt.date(2024, 1, 1), dt.date(2026, 10, 1))]
        K = {}
        with cf.ThreadPoolExecutor(8) as ex:
            for s, ym, a in ex.map(lambda j: klines_month(*j), jobs):
                if a is not None and len(a):
                    K.setdefault(s, []).append(a)
        K = {s: np.concatenate(sorted(v, key=lambda x: x[0, 0])) for s, v in K.items()}
        for s, a in sorted(K.items()):
            print(f"{s:18s} {len(a):6d} ч  {dt.datetime.utcfromtimestamp(a[0, 0]):%Y-%m-%d} – "
                  f"{dt.datetime.utcfromtimestamp(a[-1, 0]):%Y-%m-%d}")
        pickle.dump(K, open(f"{OUT}/q1h.pkl", "wb"))
    if "bvol" in what:
        days = [BV_FROM + dt.timedelta(n) for n in range((BV_TO - BV_FROM).days + 1)]
        H, miss = {}, []
        t0 = time.time()
        with cf.ThreadPoolExecutor(8) as ex:
            for n, (d, hv) in enumerate(ex.map(lambda x: bvol_day("BTCBVOLUSDT", x), days)):
                if hv is None:
                    miss.append(d)
                else:
                    H.update(hv)
                if n % 100 == 99:
                    print(f"  BVOL {n + 1}/{len(days)} дней, {time.time() - t0:.0f} с", flush=True)
        print(f"BVOL: {len(H)} часов, нет дней: {len(miss)} {miss[:10]}")
        pickle.dump(H, open(f"{OUT}/bvol.pkl", "wb"))


if __name__ == "__main__":
    main()
