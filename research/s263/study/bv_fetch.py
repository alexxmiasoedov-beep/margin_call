"""s263 — загрузка свечей премии, индекса и марк-цены TradFi-перпов: архив data.binance.vision (месячные файлы по 10.2026)
и хвост 01.11–20.11.2026 через www.binance.com/fapi (fapi.binance.com из облака отвечает 451).
Не больше ~3 запросов в секунду к архиву; при сетевых сбоях — пауза и повтор, без холостых циклов.

Запуск из /home/user/mc_data:
  python3 -I <путь>/bv_fetch.py <kind> <interval> [символы через запятую | all] [месяц_с] [месяц_по] [tail]
  kind: premiumIndexKlines | indexPriceKlines | markPriceKlines | klines
Выход: /dev/shm/s263/bv_<kind>_<interval>.pkl — символ → массив [t, o, h, l, c, count] (float64), t — открытие, с."""
import csv
import datetime
import io
import json
import os
import pickle
import sys
import time
import urllib.error
import urllib.request
import zipfile

import numpy as np
import pandas as pd

SHM = "/dev/shm/s263"
UA = {"User-Agent": "research-script/1.0"}
UTC = datetime.timezone.utc
ARCH = "https://data.binance.vision/data/futures/um/monthly"
WEB = "https://www.binance.com/fapi/v1"
TAIL0 = int(datetime.datetime(2026, 11, 1, tzinfo=UTC).timestamp())
TAIL1 = int(datetime.datetime(2026, 11, 20, tzinfo=UTC).timestamp())
_last = [0.0]


def pace(dt=0.34):
    w = _last[0] + dt - time.time()
    if w > 0:
        time.sleep(w)
    _last[0] = time.time()


def get(url, tries=5):
    for i in range(tries):
        pace()
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60)
            return r.read(), dict(r.headers)
        except urllib.error.HTTPError as e:
            if e.code in (404, 400):
                return None, {}
            if e.code in (418, 429):
                time.sleep(60)
            else:
                time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    print("  нет ответа:", url, flush=True)
    return None, {}


def parse_csv(raw):
    rows = []
    for r in csv.reader(io.StringIO(raw)):
        if not r or not r[0][:1].isdigit():
            continue
        rows.append((int(r[0]) // 1000, float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[8])))
    return rows


def months(m0, m1):
    y, m = map(int, m0.split("-"))
    out = []
    while f"{y:04d}-{m:02d}" <= m1:
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def tail(kind, iv, sym):
    """Хвост через API: 01.11–20.11.2026, по 1500 свечей за запрос."""
    step = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}[iv]
    key = "pair" if kind == "indexPriceKlines" else "symbol"
    rows, st = [], TAIL0
    while st < TAIL1:
        url = f"{WEB}/{kind}?{key}={sym}USDT&interval={iv}&startTime={st * 1000}&endTime={(TAIL1 - 1) * 1000}&limit=1500"
        raw, hd = get(url)
        if raw is None:
            break
        js = json.loads(raw)
        if not js:
            break
        rows += [(int(x[0]) // 1000, float(x[1]), float(x[2]), float(x[3]), float(x[4]), float(x[8])) for x in js]
        st = int(js[-1][0]) // 1000 + step
        w = int(hd.get("x-mbx-used-weight-1m", hd.get("X-Mbx-Used-Weight-1m", 0)) or 0)
        if w > 1500:
            time.sleep(30)
    return rows


def main():
    kind, iv = sys.argv[1], sys.argv[2]
    sel = sys.argv[3] if len(sys.argv) > 3 else "all"
    m0 = sys.argv[4] if len(sys.argv) > 4 else "2025-12"
    m1 = sys.argv[5] if len(sys.argv) > 5 else "2026-10"
    do_tail = (sys.argv[6] if len(sys.argv) > 6 else "tail") == "tail"
    meta = pd.read_csv("s263/tf_meta.csv")
    if sel == "all":
        syms = list(meta.sym[meta.k_n > 0]) + ["PAXG", "XAUT"]
    else:
        syms = sel.split(",")
    on = {r.sym: r.onboard for r in meta.itertuples()}
    out_p = f"{SHM}/bv_{kind}_{iv}.pkl"
    out = pickle.load(open(out_p, "rb")) if os.path.exists(out_p) else {}
    t0 = time.time()
    for j, s in enumerate(syms):
        rows = []
        first = datetime.datetime.fromtimestamp(on.get(s, 0), UTC).strftime("%Y-%m") if s in on else m0
        for m in months(max(m0, first), m1):
            url = f"{ARCH}/{kind}/{s}USDT/{iv}/{s}USDT-{iv}-{m}.zip"
            raw, _ = get(url)
            if raw is None:
                continue
            z = zipfile.ZipFile(io.BytesIO(raw))
            rows += parse_csv(z.read(z.namelist()[0]).decode())
        if do_tail:
            rows += tail(kind, iv, s)
        if rows:
            a = np.array(sorted(set(rows)), dtype=np.float64)
            out[s] = a
        if j % 20 == 0 or j == len(syms) - 1:
            pickle.dump(out, open(out_p, "wb"), protocol=4)
            print(f"{j + 1}/{len(syms)} {s}: строк {len(rows)}; {time.time() - t0:.0f} с", flush=True)
    pickle.dump(out, open(out_p, "wb"), protocol=4)
    print("готово:", out_p, len(out), flush=True)


if __name__ == "__main__":
    main()
