#!/usr/bin/env python3
"""s204: что было с ценой ДО суточных флагов Upbit (D и V) — только описательно, доходы после флага не считаются.

Окно подсчёта V/D/C у Upbit — 24 ч до 09:00 KST (00:00 UTC), флаг объявляется в 10:00 KST (01:00 UTC).
Дневная свеча Upbit (сутки с 09:00 KST = 00:00 UTC) совпадает с этим окном: для флага в сутки d
окно = свеча d-1 (r0), до неё — свеча d-2 (r1). Сравниваем с обычными сутками тех же монет.

Свечи: GET https://api.upbit.com/v1/candles/days?market=KRW-XXX&count=200&to=... (без ключа),
кэш /home/user/mc_data/s204/upbit_days/<монета>.json.
"""
import csv, json, os, time, statistics, collections, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timedelta, date

OUT = "/home/user/mc_data/s204"
CACHE = OUT + "/upbit_days"
UA = {"User-Agent": "research-script/1.0", "Accept": "application/json"}


def fetch(coin):
    path = f"{CACHE}/{coin}.json"
    if os.path.exists(path):
        return json.load(open(path))
    rows = {}
    for to in ("2026-11-19T00:00:00Z", "2026-05-05T00:00:00Z"):
        u = "https://api.upbit.com/v1/candles/days?" + urllib.parse.urlencode({"market": "KRW-" + coin, "count": 200, "to": to})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
                    for c in json.loads(r.read()):
                        rows[c["candle_date_time_utc"][:10]] = [c["opening_price"], c["high_price"], c["low_price"],
                                                                c["trade_price"], c["candle_acc_trade_price"]]
                break
            except urllib.error.HTTPError as e:
                if e.code == 404:      # рынок снят с торгов — без повторов
                    print("нет рынка", coin, flush=True)
                    break
                print("ошибка", coin, e, flush=True)
                time.sleep(5 * (attempt + 1))
            except Exception as e:
                print("ошибка", coin, e, flush=True)
                time.sleep(5 * (attempt + 1))
        time.sleep(0.2)
    json.dump(rows, open(path, "w"))
    return rows


def q(v, p):
    v = sorted(v)
    return v[int(p * (len(v) - 1))] if v else float("nan")


def main():
    os.makedirs(CACHE, exist_ok=True)
    ev = {}
    for k in ("D", "V"):
        ev[k] = [x for x in csv.DictReader(open(f"{OUT}/upbit_days_{k}.csv")) if x["new_episode"] == "1"]
    coins = sorted({x["coin"] for k in ev for x in ev[k]})
    print("монет", len(coins), flush=True)
    C = {c: fetch(c) for c in coins}
    allday = []      # обычные сутки тех же монет (с 24.03 по 18.11)
    for c in coins:
        for d, (o, h, l, cl, v) in C[c].items():
            if "2026-03-23" <= d <= "2026-11-18" and o:
                allday.append(cl / o - 1)
    def stats(name, xs):
        xs = [x for x in xs if x == x]
        if not xs:
            return
        print(f"{name}: n {len(xs)}, медиана {statistics.median(xs) * 100:+.2f}%, среднее {sum(xs) / len(xs) * 100:+.2f}%, "
              f"квартили {q(xs, .25) * 100:+.1f}…{q(xs, .75) * 100:+.1f}%, доля ≥ +10% {sum(x >= .10 for x in xs) / len(xs):.0%}, "
              f"≥ +20% {sum(x >= .20 for x in xs) / len(xs):.0%}, ≤ −10% {sum(x <= -.10 for x in xs) / len(xs):.0%}, "
              f"< 0 {sum(x < 0 for x in xs) / len(xs):.0%}")
    stats("обычные сутки тех же монет", allday)
    Vset = {(x["coin"], x["day"]) for x in csv.DictReader(open(f"{OUT}/upbit_days_V.csv"))}
    for k in ("D", "V"):
        r0, r1, vr, groups = [], [], [], collections.defaultdict(list)
        for x in ev[k]:
            d = date.fromisoformat(x["day"])
            c0 = C[x["coin"]].get((d - timedelta(days=1)).isoformat())
            c1 = C[x["coin"]].get((d - timedelta(days=2)).isoformat())
            if not c0 or not c0[0]:
                continue
            a = c0[3] / c0[0] - 1
            r0.append(a)
            groups[f"L{x['level']}"].append(a)
            if k == "D":
                groups["D+V" if (x["coin"], x["day"]) in Vset else "D без V"].append(a)
                groups["перп" if x["binance_perp_1d"] == "1" else "без перпа"].append(a)
            if c1 and c1[0]:
                r1.append(c1[3] / c1[0] - 1)
            # оборот окна к медиане оборота 7 предыдущих суток
            prev = [C[x["coin"]].get((d - timedelta(days=i)).isoformat()) for i in range(2, 9)]
            pv = [p[4] for p in prev if p]
            if len(pv) >= 4 and statistics.median(pv) > 0:
                vr.append(c0[4] / statistics.median(pv))
        print(f"\n{k}: новые эпизоды")
        stats(f"  {k}: сутки окна подсчёта (d−1, 00–24 UTC)", r0)
        stats(f"  {k}: сутки до окна (d−2)", r1)
        if vr:
            print(f"  {k}: оборот Upbit в окне к медиане 7 суток до: медиана ×{statistics.median(vr):.2f}, "
                  f"доля ≥ ×3 {sum(v >= 3 for v in vr) / len(vr):.0%}, ≤ ×1 {sum(v <= 1 for v in vr) / len(vr):.0%}")
        for g in sorted(groups):
            stats(f"    {k} {g}", groups[g])


if __name__ == "__main__":
    main()
