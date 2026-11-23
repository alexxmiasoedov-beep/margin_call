"""s252 — дата первого спота Binance для монет перпов (чтобы знать, когда перп был «без спота»): пары монеты из exchangeInfo
спота (TRADING и BREAK; к USDT, USDC, FDUSD, BTC, BNB, ETH, TRY, EUR), первая дневная свеча `/api/v3/klines?startTime=0&limit=1`
(data-api.binance.vision, без ключа, не чаще 4 запросов в секунду). Перпы — s2/k2y.pkl (869) и живые из constituents.json.
Итог — /home/user/mc_data/s252/spot_dates.json: {монета: первая свеча спота (unix) или null — спота не было}.
Запуск: cd /home/user/mc_data && python3 -I <repo>/research/s252/study/spot_dates.py"""
import json
import os
import pickle
import re
import time
import urllib.request

UA = {"User-Agent": "research-script/1.0"}
Q = ("USDT", "USDC", "FDUSD", "BTC", "BNB", "ETH", "TRY", "EUR", "BUSD")


def base(fs):
    m = re.match(r"^(1000000|100000|10000|1000|1M)(.+)$", fs)
    if m and not m.group(2)[0].isdigit():
        return m.group(2)
    return fs


def first(sym):
    for i in range(4):
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(
                f"https://data-api.binance.vision/api/v3/klines?symbol={urllib.request.quote(sym)}&interval=1d&startTime=0&limit=1",
                headers=UA), timeout=30).read())
            time.sleep(0.25)
            return int(d[0][0]) // 1000 if d else None
        except Exception:  # noqa: BLE001
            time.sleep(2 + 2 * i)
    return None


def main():
    sp = json.load(open("s252/spot_exinfo.json"))["symbols"]
    by = {}
    for s in sp:
        if s["quoteAsset"] in Q:
            by.setdefault(s["baseAsset"], []).append(s["symbol"])
    K = pickle.load(open("s2/k2y.pkl", "rb"))
    coins = {base(fs) for fs in K} | {v["coin"] for v in json.load(open("s252/constituents.json")).values()}
    out = json.load(open("s252/spot_dates.json")) if os.path.exists("s252/spot_dates.json") else {}
    for c in sorted(coins):
        if c in out:
            continue
        syms = by.get(c, [])
        ts = [t for t in (first(s) for s in syms) if t]
        out[c] = min(ts) if ts else None
        if len(out) % 50 == 0:
            json.dump(out, open("s252/spot_dates.json", "w"))
            print(len(out), c, out[c], flush=True)
    json.dump(out, open("s252/spot_dates.json", "w"))
    print("монет:", len(out), "без спота:", sum(1 for v in out.values() if v is None))


if __name__ == "__main__":
    main()
