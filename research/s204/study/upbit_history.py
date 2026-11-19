#!/usr/bin/env python3
"""s204: история рыночных предупреждений Upbit (страница «시장경보 현황»).

Скрытый ключ: страница https://upbit.com/service_center/market_warning_history берёт данные
из открытого (без ключа) эндпоинта
  GET https://crix-api-cdn.upbit.com/v1/crix/market-event-records
      ?quoteCurrencyCode=KRW&start=YYYY-MM-DD HH:MM:SS&end=...&page=N&size<=200
      [&code=CRIX.UPBIT.KRW-XXX][&eventType=...][&warningLevel=LEVEL_1|2|3]
Ограничения сервера: окно start..end <= 30 сут, start >= сегодня - 1095 сут (на 19.11.2026 — 2023-11-20),
size <= 200. Время — UTC. Записи отсортированы по triggerTimeUtc по убыванию.

Пишет /home/user/mc_data/s204/upbit_mer/<quote>_<начало окна>_p<стр>.json.gz и сводку
/home/user/mc_data/s204/upbit_mer_<quote>.csv (без дублей).
Запуск: python3 upbit_history.py [KRW|BTC|USDT] [ГГГГ-ММ-ДД начала] [ГГГГ-ММ-ДД ЧЧ:ММ конца]
"""
import csv, gzip, json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta

OUT = "/home/user/mc_data/s204"
UA = {"User-Agent": "research-script/1.0", "Accept": "application/json"}
URL = "https://crix-api-cdn.upbit.com/v1/crix/market-event-records"
PAUSE = 1.5


def get(params):
    u = URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
                return json.loads(r.read())
        except Exception as e:  # сеть — пауза и до трёх попыток
            print("ошибка", e, "пауза", 10 * (attempt + 1), flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("нет ответа: " + u)


def main():
    quote = sys.argv[1] if len(sys.argv) > 1 else "KRW"
    start = datetime.strptime(sys.argv[2], "%Y-%m-%d") if len(sys.argv) > 2 else datetime(2026, 3, 1)
    end = datetime.strptime(sys.argv[3], "%Y-%m-%d %H:%M") if len(sys.argv) > 3 else datetime(2026, 11, 19, 20, 0)
    os.makedirs(OUT + "/upbit_mer", exist_ok=True)
    rows = {}
    s = start
    n_req = 0
    while s < end:
        e = min(s + timedelta(days=10), end)
        page = 1
        while True:
            p = {"quoteCurrencyCode": quote, "start": s.strftime("%Y-%m-%d %H:%M:%S"),
                 "end": e.strftime("%Y-%m-%d %H:%M:%S"), "page": page, "size": 200}
            d = get(p)
            n_req += 1
            with gzip.open(f"{OUT}/upbit_mer/{quote}_{s:%Y%m%d}_p{page:03d}.json.gz", "wt") as f:
                json.dump(d, f, ensure_ascii=False)
            if "error" in d:
                print(s, "ошибка сервера", d["error"], flush=True)
                break
            L = d.get("list") or []
            for r in L:
                k = (r.get("code"), r.get("eventType"), r.get("warningLevel"), r.get("triggerTimeUtc"))
                rows[k] = r
            tp = d.get("totalPage") or 0
            print(quote, s.date(), e.date(), "стр", page, "/", tp, "всего", d.get("totalCount"), "записей", len(rows),
                  flush=True)
            time.sleep(PAUSE)
            if page >= tp or not L:
                break
            page += 1
        s = e
    keys = ["code", "quoteCurrencyCode", "eventType", "warningLevel", "triggerType", "triggerTimeUtc",
            "expirationTimeUtc"]
    extra = sorted({k for r in rows.values() for k in r} - set(keys))
    with open(f"{OUT}/upbit_mer_{quote}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(keys + extra)
        for r in sorted(rows.values(), key=lambda r: (r.get("triggerTimeUtc"), r.get("code"))):
            w.writerow([r.get(k, "") for k in keys + extra])
    print("готово: запросов", n_req, "записей", len(rows), "лишние поля", extra, flush=True)


if __name__ == "__main__":
    main()
