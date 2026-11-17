"""s88 — данные для проверки вне выборки (01.10.2022–30.09.2024; с запасом 09.2022–10.2024):
- часовые свечи и фандинг фьючерсов USDT-M из архива data.binance.vision у монет, торгующихся к воне на Upbit или Bithumb;
- часовые свечи этих рынков к воне на Upbit и Bithumb (API бирж; снятые рынки биржи не отдают — 404) и KRW-BTC Upbit
  для курса воны.
Результат — s88/oos/: fut/<фьючерс>.pkl {t, o, h, l, c, qv, f: [[время, ставка]]}, kc/<биржа>/<рынок>.pkl {t, c, v},
map.pkl {монета: фьючерс}. Прерванный сбор продолжается с места остановки (сбой сети не кэшируется).

Запуск из папки с данными: python3 <путь>/s88/oos_fetch.py"""
import datetime
import io
import os
import pickle
import re
import sys
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
from kr_listings import API, get, iso, utc  # noqa: E402

UTC = datetime.timezone.utc
T0, T1 = datetime.datetime(2022, 9, 1, tzinfo=UTC), datetime.datetime(2024, 10, 4, tzinfo=UTC)
MONTHS = [f"{y}-{m:02d}" for y in (2022, 2023, 2024) for m in range(1, 13) if "2022-09" <= f"{y}-{m:02d}" <= "2024-10"]
OUT = "s88/oos"
VIS = "https://data.binance.vision/data/futures/um/monthly"
LIST = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix=data/futures/um/monthly/klines/"
ERR = object()


def http(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "margin-call research"}), timeout=timeout).read()


def um_symbols():
    syms, marker = [], ""
    while True:
        x = http(LIST + (f"&marker={marker}" if marker else ""), 30).decode()
        p = re.findall(r"<Prefix>data/futures/um/monthly/klines/([^/<]+)/</Prefix>", x)
        syms += p
        if "<IsTruncated>true</IsTruncated>" not in x or not p:
            return set(syms)
        marker = f"data/futures/um/monthly/klines/{p[-1]}/"


def vis(path):
    """CSV из архива: текст, None — файла нет (404), ERR — сбой сети."""
    for i in range(5):
        try:
            z = zipfile.ZipFile(io.BytesIO(http(VIS + path)))
            return z.read(z.namelist()[0]).decode()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
        time.sleep(2 * (i + 1))
    return ERR


def fut(sym):
    path = f"{OUT}/fut/{sym}.pkl"
    if os.path.exists(path):
        return True
    K, F = [], []
    for m in MONTHS:
        k = vis(f"/klines/{sym}/1h/{sym}-1h-{m}.zip")
        f = vis(f"/fundingRate/{sym}/{sym}-fundingRate-{m}.zip")
        if k is ERR or f is ERR:
            return False
        if k:
            K += [r.split(",") for r in k.strip().splitlines() if r[:1].isdigit()]
        if f:
            F += [r.split(",") for r in f.strip().splitlines() if r[:1].isdigit()]
    res = None
    if K:
        a = np.array([[float(r[i]) for i in (0, 1, 2, 3, 4, 7)] for r in K])
        a = a[np.argsort(a[:, 0], kind="stable")]
        _, u = np.unique(a[:, 0], return_index=True)
        a = a[u]
        fr = np.array(sorted((int(float(r[0])) // 1000, float(r[-1])) for r in F)) if F else np.zeros((0, 2))
        res = {"t": (a[:, 0] // 1000).astype(np.int64), "o": a[:, 1], "h": a[:, 2], "l": a[:, 3], "c": a[:, 4],
               "qv": a[:, 5], "f": fr}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pickle.dump(res, open(path + ".tmp", "wb")); os.replace(path + ".tmp", path)
    return True


def kr(ex, market):
    path = f"{OUT}/kc/{ex}/{market}.pkl"
    if os.path.exists(path):
        return True
    rows, to = {}, T1
    while to > T0:
        c = get(f"{API[ex]}/v1/candles/minutes/60?market={market}&count=200&to={iso(to, ex)}"); time.sleep(0.12)
        if c is None and rows:                                 # рынок есть, а запрос не прошёл — сбой, не кэшируем
            return False
        if not c:
            break
        for x in c:
            rows[int(utc(x).timestamp())] = (float(x["trade_price"]), float(x["candle_acc_trade_price"]))
        first = min(utc(x) for x in c)
        if len(c) < 200 or first >= to:
            break
        to = first
    res = None
    if rows:
        t = np.array(sorted(rows), dtype=np.int64)
        res = {"t": t, "c": np.array([rows[x][0] for x in t]), "v": np.array([rows[x][1] for x in t])}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pickle.dump(res, open(path + ".tmp", "wb")); os.replace(path + ".tmp", path)
    return True


def main():
    os.makedirs(OUT, exist_ok=True)
    um = um_symbols()
    bases = {}
    for ex in API:
        for m in get(f"{API[ex]}/v1/market/all") or []:
            if m["market"].startswith("KRW-"):
                bases.setdefault(m["market"][4:], set()).add(ex)
    mp = {}
    for b in bases:
        for p in ("", "1000", "1000000"):
            if p + b + "USDT" in um:
                mp[b] = p + b + "USDT"
                break
    pickle.dump(mp, open(f"{OUT}/map.pkl", "wb"))
    syms = sorted(set(mp.values()) | {"BTCUSDT"})
    jobs = [(ex, f"KRW-{b}") for b in sorted(mp) for ex in sorted(bases[b])] + [("upbit", "KRW-BTC")]
    print(f"фьючерсов в архиве {len(um)}, монет к воне {len(bases)}, с фьючерсом {len(mp)}; рынков {len(jobs)}", flush=True)
    for rnd in range(3):                                       # повтор того, что не скачалось из-за сбоев
        with ThreadPoolExecutor(16) as pf, ThreadPoolExecutor(6) as pu, ThreadPoolExecutor(20) as pb:
            fs = [pf.submit(fut, s) for s in syms]
            ks = [(pu if ex == "upbit" else pb).submit(kr, ex, m) for ex, m in jobs]
            bad_f = [s for s, f in zip(syms, fs) if not f.result()]
            bad_k = [j for j, k in zip(jobs, ks) if not k.result()]
        print(f"проход {rnd + 1}: не скачано фьючерсов {len(bad_f)}, рынков {len(bad_k)}", flush=True)
        if not bad_f and not bad_k:
            break
        syms, jobs = bad_f, bad_k
        time.sleep(60)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
