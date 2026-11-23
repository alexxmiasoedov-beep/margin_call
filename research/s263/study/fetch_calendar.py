"""s263 — календари Nasdaq без ключа (api.nasdaq.com, публичный JSON страницы календаря): отчётности (earnings)
и экс-дивидендные даты (dividends) по дням. Берутся только тикеры, у которых есть TradFi-перп Binance.
~1 запрос в секунду; при сбое — пауза и повтор.

Запуск из /home/user/mc_data: python3 -I <путь>/fetch_calendar.py [с 2026-05-01] [по 2026-12-31]
Выход: s263/calendar_earnings.csv, s263/calendar_dividends.csv."""
import datetime
import json
import subprocess
import sys
import time

import pandas as pd

UA = {"User-Agent": "research-script/1.0", "Accept": "application/json"}
ALIAS = {"BRKB": "BRK.B", "GOOGL": "GOOGL"}


def get(url):
    """Через curl (urllib получает 403 от пограничного узла Nasdaq, curl с тем же User-Agent — 200)."""
    for i in range(4):
        time.sleep(1.0)
        r = subprocess.run(["curl", "-s", "-m", "40", "-A", UA["User-Agent"], "-H", "Accept: application/json", url],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.startswith("{"):
            try:
                return json.loads(r.stdout)
            except ValueError:
                pass
        time.sleep(5 * (i + 1))
    return None


def main():
    d0 = datetime.date.fromisoformat(sys.argv[1] if len(sys.argv) > 1 else "2026-05-01")
    d1 = datetime.date.fromisoformat(sys.argv[2] if len(sys.argv) > 2 else "2026-12-31")
    meta = pd.read_csv("s263/tf_meta.csv")
    us = set(meta.sym[meta.ut == "EQUITY"])
    tick = {ALIAS.get(s, s): s for s in us}
    er, dv = [], []
    d = d0
    while d <= d1:
        if d.weekday() < 5:
            j = get(f"https://api.nasdaq.com/api/calendar/earnings?date={d.isoformat()}")
            for r in (((j or {}).get("data") or {}).get("rows") or []):
                s = tick.get(r.get("symbol"))
                if s:
                    er.append(dict(date=d.isoformat(), sym=s, time=r.get("time"), eps=r.get("eps"),
                                   surprise=r.get("surprise"), fq=r.get("fiscalQuarterEnding")))
            j = get(f"https://api.nasdaq.com/api/calendar/dividends?date={d.isoformat()}")
            cal = (((j or {}).get("data") or {}).get("calendar") or {})
            for r in (cal.get("rows") or []):
                s = tick.get(r.get("symbol"))
                if s:
                    dv.append(dict(date=d.isoformat(), sym=s, ex=r.get("dividend_Ex_Date"), rate=r.get("dividend_Rate"),
                                   annual=r.get("indicated_Annual_Dividend"), pay=r.get("payment_Date")))
        d += datetime.timedelta(1)
        if d.day == 1:
            print(d, len(er), len(dv), flush=True)
    pd.DataFrame(er).to_csv("s263/calendar_earnings.csv", index=False)
    pd.DataFrame(dv).to_csv("s263/calendar_dividends.csv", index=False)
    print("отчётностей:", len(er), "дивидендов:", len(dv))


if __name__ == "__main__":
    main()
