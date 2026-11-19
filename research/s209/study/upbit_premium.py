#!/usr/bin/env python3
"""s209: история «премии Upbit» по монетам (вкладка «업비트 프리미엄» карточки монеты и DataLab).

Ключ: бандл upbit.com (`sri-v2-chunk-*.js`) → RTK-запрос premiumRecords →
  GET https://crix-api-cdn.upbit.com/v1/crix/price_difference/premium_records
      ?code=CRIX.UPBIT.KRW-XXX&timeUnit=DAYS_1|MINUTES_60&count<=200&to=ГГГГ-ММ-ДДTЧЧ:ММ:СС (UTC, не включая)
Без ключа. Записи с 2024-06-19 (раньше — «데이터를 준비하고 있습니다»). Поля: disparityRate (премия монеты, %),
btcDisparityRate, usdtDisparityRate (премии BTC и USDT в тот же момент), btcRealDisparityRate,
usdtRealDisparityRate (премия монеты сверх премии BTC / USDT), recordTime (UTC), recordTimeKst.

Запуск: python3 upbit_premium.py [DAYS_1|MINUTES_60] [макс. рынков]
Пишет /home/user/mc_data/s209/upbit_premium/<timeUnit>/<рынок>.json.gz и сводку upbit_premium_<timeUnit>.csv.gz.
"""
import csv, gzip, io, json, os, sys, time
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common209 import jget, perp_bases

OUT = "/home/user/mc_data/s209/upbit_premium"
URL = "https://crix-api-cdn.upbit.com/v1/crix/price_difference/premium_records"
START = datetime(2024, 6, 1)


def markets():
    c, j = jget("https://api.upbit.com/v1/market/all", {"isDetails": "false"})
    return sorted(m["market"] for m in j if m["market"].startswith("KRW-"))


def main():
    tu = sys.argv[1] if len(sys.argv) > 1 else "DAYS_1"
    lim = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 6
    step = timedelta(days=200) if tu == "DAYS_1" else timedelta(hours=200)
    perps = perp_bases()
    mk = [m for m in markets() if m[4:] in perps][:lim]
    print("рынков KRW с перпом Binance:", len(mk), flush=True)
    os.makedirs(f"{OUT}/{tu}", exist_ok=True)
    allrows, nreq, t0 = [], 0, time.time()
    for i, m in enumerate(mk):
        fn = f"{OUT}/{tu}/{m}.json.gz"
        if os.path.exists(fn):
            recs = json.load(gzip.open(fn, "rt"))
        else:
            recs, to, solely = [], datetime.utcnow() + timedelta(days=1), False
            while to > START:
                c, j = jget(URL, {"code": "CRIX.UPBIT." + m, "timeUnit": tu, "count": 200,
                                  "to": to.strftime("%Y-%m-%dT%H:%M:%S")}, gap=0.15)
                nreq += 1
                if c != 200 or not isinstance(j, dict):
                    print(m, "ошибка", c, str(j)[:120], flush=True)
                    time.sleep(5)
                    break
                r = j.get("records") or []
                solely = solely or bool(j.get("isSolelyListed"))
                if not r:
                    break
                recs.extend(r)
                oldest = min(datetime.strptime(x["recordTime"], "%Y-%m-%dT%H:%M:%S") for x in r)
                if oldest >= to:
                    break
                to = oldest
                if len(r) < 200:
                    break
            with gzip.open(fn, "wt") as f:
                json.dump(recs, f)
        for x in recs:
            allrows.append([m] + [x.get(k) for k in ("recordTime", "disparityRate", "btcDisparityRate",
                                                     "usdtDisparityRate", "btcRealDisparityRate",
                                                     "usdtRealDisparityRate")])
        if i % 25 == 0:
            print(f"{i+1}/{len(mk)} {m} записей {len(recs)} запросов {nreq} за {time.time()-t0:.0f} с", flush=True)
    allrows.sort()
    with gzip.open(f"/home/user/mc_data/s209/upbit_premium_{tu}.csv.gz", "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["market", "time_utc", "disparity", "btc_disparity", "usdt_disparity", "btc_real", "usdt_real"])
        w.writerows(allrows)
    ts = [r[1] for r in allrows]
    print(f"готово: рынков {len(mk)}, строк {len(allrows)}, даты {min(ts)} … {max(ts)}, запросов {nreq}, "
          f"{time.time()-t0:.0f} с", flush=True)


if __name__ == "__main__":
    main()
