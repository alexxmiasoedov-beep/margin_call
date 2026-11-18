"""s157 — дневные признаки опционов Deribit (BTC, ETH) по всем сделкам history.deribit.com (без ключа), 10.2020–11.2026.
Сделки без блок-сделок, комбо и ликвидаций. Дельта — по Блэку-76 (F = index_price, IV сделки, срок до экспирации 08:00 UTC).
Признаки суток UTC: rr25 — медиана IV коллов с Δ 0,20–0,30 минус медиана IV путов с Δ −0,30…−0,20 (срок 7–45 сут, ≥ 5 сделок
каждого вида); atm — медиана IV при |Δ| 0,4–0,6 (7–45 сут); put_net, call_net — Σ (покупка тейкера − продажа) премии в $
по внеденежным (|Δ| < 0,4) путам и коллам сроком до 90 сут; prem — вся премия в $; n — число сделок. Итог — дописывается
в s157/daily_feat.jsonl папки данных, прерванная выгрузка продолжается. 8 потоков.
Запуск из /home/user/mc_data: python3 <repo>/research/s157/daily_feat.py"""
import datetime as dt
import json
import math
import os
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "research-script/1.0"}
OUTF = "s157/daily_feat.jsonl"
MON = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
LOCK = threading.Lock()


def get(url, tries=8):
    for k in range(tries):
        try:
            return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())
        except Exception:
            time.sleep(2 * (k + 1))
    return None


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def parse(inst):
    m = re.match(r"^[A-Z]+-(\d{1,2})([A-Z]{3})(\d{2})-([\dd\.]+)-([CP])$", inst)
    if not m:
        return None
    d, mon, y, k, cp = m.groups()
    exp = dt.datetime(2000 + int(y), MON[mon], int(d), 8, tzinfo=dt.timezone.utc).timestamp()
    return exp, float(k.replace("d", ".")), cp


def day_feat(cur, day):
    st = int(dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
    en = st + 86400_000
    cursor, seen = st, set()
    c25, p25, atm = [], [], []
    put_net = call_net = prem = 0.0
    n = 0
    while True:
        r = get(f"https://history.deribit.com/api/v2/public/get_last_trades_by_currency_and_time?currency={cur}&kind=option"
                f"&start_timestamp={cursor}&end_timestamp={en}&count=1000&sorting=asc")
        if r is None:
            return None
        tr = r["result"]["trades"]
        new = [x for x in tr if x["trade_id"] not in seen]
        for x in new:
            seen.add(x["trade_id"])
            if x.get("block_trade_id") or x.get("combo_id") or x.get("liquidation"):
                continue
            p = parse(x["instrument_name"])
            if not p or not x.get("iv") or not x.get("index_price"):
                continue
            exp, K, cp = p
            T = (exp - x["timestamp"] / 1000) / 86400
            if T <= 0:
                continue
            F, sig = float(x["index_price"]), float(x["iv"]) / 100
            if sig <= 0 or K <= 0:
                continue
            d1 = (math.log(F / K) + 0.5 * sig * sig * T / 365) / (sig * math.sqrt(T / 365))
            delta = ncdf(d1) - (0 if cp == "C" else 1)
            usd = float(x["price"]) * float(x["amount"]) * F
            sgn = 1 if x["direction"] == "buy" else -1
            n += 1; prem += usd
            if 7 <= T <= 45:
                if cp == "C" and 0.20 <= delta <= 0.30:
                    c25.append(x["iv"])
                elif cp == "P" and -0.30 <= delta <= -0.20:
                    p25.append(x["iv"])
                if 0.4 <= abs(delta) <= 0.6:
                    atm.append(x["iv"])
            if T <= 90 and abs(delta) < 0.4:
                if cp == "P":
                    put_net += sgn * usd
                else:
                    call_net += sgn * usd
        if not r["result"].get("has_more") or not tr:
            break
        last = tr[-1]["timestamp"]
        cursor = last if new else last + 1

    def med(v):
        v = sorted(v)
        return v[len(v) // 2] if v else None
    rr = (med(c25) - med(p25)) if len(c25) >= 5 and len(p25) >= 5 else None
    return dict(cur=cur, day=day, rr25=rr, atm=med(atm) if len(atm) >= 5 else None, put_net=put_net, call_net=call_net,
                prem=prem, n=n, nc25=len(c25), np25=len(p25))


def main():
    os.makedirs("s157", exist_ok=True)
    done = set()
    if os.path.exists(OUTF):
        for ln in open(OUTF):
            r = json.loads(ln); done.add((r["cur"], r["day"]))
    d0, d1 = dt.date(2020, 9, 1), dt.date(2026, 11, 17)
    days = [(d0 + dt.timedelta(k)).isoformat() for k in range((d1 - d0).days)]
    todo = [(c, d) for d in days for c in ("BTC", "ETH") if (c, d) not in done]
    print("к выгрузке", len(todo), flush=True)
    k = 0

    def one(cd):
        return day_feat(*cd)
    with ThreadPoolExecutor(8) as ex:
        for r in ex.map(one, todo):
            k += 1
            if r:
                with LOCK:
                    open(OUTF, "a").write(json.dumps(r) + "\n")
            if k % 200 == 0:
                print(k, "из", len(todo), flush=True)
    print("готово", flush=True)


if __name__ == "__main__":
    main()
