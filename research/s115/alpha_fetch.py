"""s115 — часовые свечи Binance Alpha к USDT для токенов с фьючерсом Binance (список s18/alpha.json, сопоставление по тикеру
с поправкой 1000x). Документированный API рыночных данных Alpha: bapi/defi/v1/public/alpha-trade/klines (limit 1500).
Кэш — s115/alpha/<тикер фьючерса>.json: [[время открытия мс, …, объём в токенах, …, оборот в USDT, сделок, …]].
Запуск из папки с данными: python3 <repo>/research/s115/alpha_fetch.py"""
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "s15"))
from common import K  # noqa: E402

URL = "https://www.binance.com/bapi/defi/v1/public/alpha-trade/klines?symbol={}&interval=1h&limit=1500&startTime={}"
START, END = 1733011200000, 1792368000000          # 01.12.2024 … 18.10.2026


def get(url):
    for k in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return json.loads(urllib.request.urlopen(req, timeout=40).read())
        except Exception:
            time.sleep(2 + 3 * k)
    return None


def one(job):
    fut, aid = job
    path = f"s115/alpha/{fut}.json"
    if os.path.exists(path):
        return 0
    rows, st = [], START
    while st < END:
        r = get(URL.format(aid + "USDT", st))
        if r is None:
            return 0                                          # сбой сети — не кэшируем
        if not r.get("success") or not r.get("data"):
            break
        d = r["data"]
        rows += d
        nxt = int(d[-1][0]) + 3600 * 1000
        if nxt <= st or len(d) < 1500:
            break
        st = nxt
        time.sleep(0.2)
    json.dump(rows, open(path, "w"))
    return 1


def main():
    L = json.load(open("s18/alpha.json"))["data"]
    base = {re.sub(r"^(1000000|100000|10000|1000)", "", s): s for s in K}
    jobs = sorted({(base[str(x["symbol"]).upper()], x["alphaId"]) for x in L if str(x.get("symbol", "")).upper() in base})
    os.makedirs("s115/alpha", exist_ok=True)
    with ThreadPoolExecutor(4) as ex:
        n = sum(ex.map(one, jobs))
    ok = sum(1 for f in os.listdir("s115/alpha") if os.path.getsize(f"s115/alpha/{f}") > 10)
    print(f"токенов: {len(jobs)}, скачано сейчас: {n}, с непустыми свечами: {ok}", flush=True)


if __name__ == "__main__":
    main()
