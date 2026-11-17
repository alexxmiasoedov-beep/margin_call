"""s136 — дневные снимки CoinMarketCap (топ-200) за 01.07.2020–16.11.2026 из открытого data-api без ключа:
ранг, капитализация, монеты в обращении, цена, оборот. Кэш — s136/raw/<дата>.json (по строке на монету:
[id, symbol, rank, marketCap, circulatingSupply, price, volume24h]); прерванная загрузка продолжается.
Пауза 2,5 с между запросами. Запуск из папки с данными: python3 <repo>/research/s136/cmc_hist.py"""
import datetime
import json
import os
import time
import urllib.request

URL = ("https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listings/historical?date={}&start=1&limit=200"
       "&convertId=2781")
OUT = "s136/raw"
D0, D1 = datetime.date(2020, 7, 1), datetime.date(2026, 11, 16)


def get(day):
    for i in range(5):
        try:
            req = urllib.request.Request(URL.format(day), headers={"User-Agent": "research-script/1.0"})
            x = json.loads(urllib.request.urlopen(req, timeout=40).read())
            rows = []
            for r in x.get("data") or []:
                q = (r.get("quotes") or [{}])[0]
                rows.append([r["id"], r["symbol"], r["cmcRank"], q.get("marketCap"), r.get("circulatingSupply"),
                             q.get("price"), q.get("volume24h")])
            return rows
        except Exception as e:                                # сеть ненадёжна — пауза и повтор
            print(day, "ошибка", type(e).__name__, flush=True)
            time.sleep(10 * (i + 1))
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    day, n = D0, 0
    while day <= D1:
        p = f"{OUT}/{day}.json"
        if not os.path.exists(p):
            rows = get(day)
            if rows:
                json.dump(rows, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)
            n += 1
            if n % 100 == 0:
                print(day, n, flush=True)
            time.sleep(2.5)
        day += datetime.timedelta(days=1)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
