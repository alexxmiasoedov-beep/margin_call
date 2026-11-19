#!/usr/bin/env python3
"""s204: история «경보제» Bithumb с июля 2023 г.

Скрытый ключ: страница «투자경보 안내 → 경보 내역» сайта Bithumb (скрипт BYTylWJd.chunk.js) берёт данные из
  GET https://gw.bithumb.com/exchange/v2/trade/virtual-asset/warning/history
      ?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD&crncCd=C0100(KRW)&warningType=01..05&warningLevel=CAUTION|WARNING|DANGER
      &size<=100&cursor=<nextCursor>
Сайт требует выбрать монету, сервер — нет. Окно startDate..endDate <= ~180 сут; записи — только закончившиеся,
время — KST (UTC+9). Коды: 01 цена (шаг 10/20/30 рост, 11/21/31 падение), 02 объём, 03 депозиты,
04 разница с CoinMarketCap (10/20/30 выше, 11/21/31 ниже), 05 концентрация счетов.
Пороги — поле meta (те же /v2/trade/virtual-asset/warning).

Пишет /home/user/mc_data/s204/bithumb_gw/hist/<тип>_<начало окна>_p<стр>.json.gz и /home/user/mc_data/s204/bithumb_hist.csv.
Запуск: python3 bithumb_history.py 03,02,05,01,04 [уровень 1|2|3] [ГГГГ-ММ-ДД начала]
Без warningLevel сервер отдаёт только уровень 1 (주의); уровни 2 (경고) и 3 (위험) есть с 29.01.2026 и
пишутся в отдельный файл bithumb_hist_L<уровень>.csv.
"""
import csv, gzip, json, os, sys, time, urllib.parse, urllib.request
from datetime import date, timedelta

OUT = "/home/user/mc_data/s204"
URL = "https://gw.bithumb.com/exchange/v2/trade/virtual-asset/warning/history"
UA = {"User-Agent": "Mozilla/5.0 (research-script/1.0)", "Accept": "application/json"}
PAUSE = float(os.environ.get("PAUSE", "1.0"))


def get(params):
    u = URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
                return json.loads(r.read())
        except Exception as e:
            print("ошибка", repr(e)[:150], "пауза", 15 * (attempt + 1), flush=True)
            time.sleep(15 * (attempt + 1))
    raise RuntimeError("нет ответа " + u)


def main():
    types = (sys.argv[1] if len(sys.argv) > 1 else "03,02,05,01,04").split(",")
    level = sys.argv[2] if len(sys.argv) > 2 else ""
    start0 = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else date(2023, 7, 1)
    os.makedirs(OUT + "/bithumb_gw/hist", exist_ok=True)
    csv_path = OUT + ("/bithumb_hist.csv" if not level else f"/bithumb_hist_L{level}.csv")
    seen = set()
    if os.path.exists(csv_path):
        for r in csv.DictReader(open(csv_path)):
            seen.add((r["crncCd"], r["coinType"], r["warningType"], r["warningStep"], r["startDateTime"]))
    new_file = not os.path.exists(csv_path)
    f = open(csv_path, "a", newline="")
    w = csv.writer(f)
    keys = ["crncCd", "coinType", "warningType", "warningStep", "startDateTime", "endDateTime"]
    if new_file:
        w.writerow(keys)
    n_req = 0
    for wt in types:
        s = start0
        end = date(2026, 11, 21)
        total_t = 0
        while s <= end:
            e = min(s + timedelta(days=89), end)
            cursor = None
            page = 1
            while True:
                p = {"startDate": s.isoformat(), "endDate": e.isoformat(), "crncCd": "C0100", "warningType": wt,
                     "size": 100}
                if level:
                    p["warningLevel"] = level
                if cursor:
                    p["cursor"] = cursor
                d = get(p)
                n_req += 1
                with gzip.open(f"{OUT}/bithumb_gw/hist/{wt}{'L' + level if level else ''}_{s:%Y%m%d}_p{page:03d}.json.gz", "wt") as g:
                    json.dump(d, g, ensure_ascii=False)
                if d.get("status") != 200:
                    print(wt, s, e, "ответ", d.get("status"), d.get("message"), flush=True)
                    break
                dd = d.get("data") or {}
                items = dd.get("items") or []
                k_new = 0
                for it in items:
                    key = (it.get("crncCd"), it.get("coinType"), it.get("warningType"), it.get("warningStep"),
                           it.get("startDateTime"))
                    if key in seen:
                        continue
                    seen.add(key)
                    w.writerow([it.get(k, "") for k in keys])
                    k_new += 1
                total_t += k_new
                extra = sorted(set().union(*[set(it) for it in items]) - set(keys)) if items else []
                print(wt, s, e, "стр", page, "записей", len(items), "новых", k_new, "всего по типу", total_t,
                      "лишние поля" if extra else "", extra if extra else "", flush=True)
                time.sleep(PAUSE)
                if not dd.get("hasNext") or not dd.get("nextCursor"):
                    break
                cursor = dd["nextCursor"]
                page += 1
            f.flush()
            s = e + timedelta(days=1)
    f.close()
    print("готово: запросов", n_req, "записей в файле", len(seen), flush=True)


if __name__ == "__main__":
    main()
