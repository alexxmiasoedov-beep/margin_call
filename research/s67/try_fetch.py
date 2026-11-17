"""s67 — часовые свечи спотовых пар к лире Binance (data.binance.vision): месяцы 2024-10…2026-09 и дни 2026-10-01…18,
плюс USDTTRY для перевода в $. Итог — s67/try1h.pkl: {пара: массив [время открытия, оборот в лирах, закрытие]}.
Запуск из папки с данными: python3 <repo>/research/s67/try_fetch.py"""
import io
import os
import pickle
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np

BASE = "https://data.binance.vision/data/spot"
S3 = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix="
MONTHS = [f"2024-{m:02d}" for m in (10, 11, 12)] + [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 10)]
DAYS = [f"2026-10-{d:02d}" for d in range(1, 19)]


def pairs():
    out, marker, prefix = [], "", "data/spot/monthly/klines/"
    while True:
        x = urllib.request.urlopen(S3 + urllib.parse.quote(prefix, safe="/") + (f"&marker={urllib.parse.quote(marker)}" if marker else ""),
                                   timeout=60).read().decode()
        ps = re.findall(r"<Prefix>([^<]+)</Prefix>", x)[1:]
        out += [p.split("/")[-2] for p in ps]
        if "<IsTruncated>true" not in x or not ps:
            break
        marker = ps[-1]
    return sorted(p for p in out if p.endswith("TRY"))


def get(url):
    for _ in range(4):
        try:
            return urllib.request.urlopen(url, timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:
            pass
    return None


def one(pair):
    rows = []
    urls = [f"{BASE}/monthly/klines/{pair}/1h/{pair}-1h-{m}.zip" for m in MONTHS] + \
           [f"{BASE}/daily/klines/{pair}/1h/{pair}-1h-{d}.zip" for d in DAYS]
    for u in urls:
        raw = get(u)
        if not raw:
            continue
        z = zipfile.ZipFile(io.BytesIO(raw))
        for ln in z.read(z.namelist()[0]).decode().splitlines():
            p = ln.split(",")
            if p and p[0].isdigit():
                t = int(p[0]); t = t // 1000 if t < 10 ** 14 else t // 1_000_000     # с 2025 г. время в микросекундах
                rows.append((t, float(p[7]), float(p[4])))
    if not rows:
        return pair, None
    a = np.array(sorted(set(rows)))
    return pair, a


def main():
    os.makedirs("s67", exist_ok=True)
    ps = pairs()
    print("пар к лире:", len(ps), flush=True)
    out = {}
    with ThreadPoolExecutor(16) as ex:
        for n, (p, a) in enumerate(ex.map(one, ps)):
            if a is not None:
                out[p] = a
            if n % 50 == 49:
                print(f"  {n + 1}/{len(ps)}", flush=True)
    pickle.dump(out, open("s67/try1h.pkl", "wb"))
    print("готово: пар со свечами", len(out), flush=True)


if __name__ == "__main__":
    main()
