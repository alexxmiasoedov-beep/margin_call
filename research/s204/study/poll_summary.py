#!/usr/bin/env python3
"""s204: сводка своей записи (poll.py) и сверка с историями бирж.

Читает /home/user/mc_data/s204/events.csv, snapshots.csv, raw/*.json.gz; список перпов —
raw/www_fapi_exchangeInfo.json. Сверка: появления/снятия на KRW-рынках Upbit — с записями
market-event-records; закончившиеся за время записи предупреждения Bithumb — с /warning/history.
"""
import csv, glob, gzip, json, collections, time, urllib.parse, urllib.request
from datetime import datetime, timedelta

OUT = "/home/user/mc_data/s204"
UA = {"User-Agent": "research-script/1.0"}


def perps():
    d = json.load(open(OUT + "/raw/www_fapi_exchangeInfo.json"))
    s = set()
    for x in d["symbols"]:
        if x.get("contractType") == "PERPETUAL" and x.get("quoteAsset") == "USDT" and x.get("underlyingType") == "COIN" \
                and x.get("status") == "TRADING":
            b = x["baseAsset"]
            for pre in ("1000000", "10000", "1000", "1M"):
                if b.startswith(pre) and len(b) > len(pre):
                    b = b[len(pre):]
                    break
            s.add(b)
    return s


def main():
    P = perps()
    S = list(csv.DictReader(open(OUT + "/snapshots.csv")))
    t0, t1 = S[0]["time_utc"], S[-1]["time_utc"]
    n_polls = len({s["time_utc"] for s in S})
    errs = sum(1 for s in S if s["http"] == "ERR")
    print(f"запись: {t0} — {t1}, опросов {n_polls}, ошибок {errs}")
    # последние снимки
    up = json.load(gzip.open(sorted(glob.glob(OUT + "/raw/upbit_2*.json.gz"))[-1]))
    bw = json.load(gzip.open(sorted(glob.glob(OUT + "/raw/bithumb_warn_2*.json.gz"))[-1]))
    ba = json.load(gzip.open(sorted(glob.glob(OUT + "/raw/bithumb_all_2*.json.gz"))[-1]))
    krw = [m for m in up if m["market"].startswith("KRW-")]
    cnt = collections.Counter()
    cntp = collections.Counter()
    coins = collections.defaultdict(set)
    for m in krw:
        ev = m["market_event"]
        c = m["market"][4:]
        fl = [k for k, v in ev["caution"].items() if v] + (["WARNING"] if ev.get("warning") else [])
        for k in fl:
            cnt[k] += 1
            cntp[k] += c in P
            coins[k].add(c)
    print(f"\nUpbit, последний снимок: рынков KRW {len(krw)}, с флагом {sum(1 for m in krw if any(m['market_event']['caution'].values()) or m['market_event'].get('warning'))}")
    for k in sorted(cnt):
        print(f"  {k}: {cnt[k]} (с перпом Binance {cntp[k]})")
    bc = collections.Counter((w["warning_type"], w["warning_step"]) for w in bw if w["market"].startswith("KRW-"))
    bcp = collections.Counter((w["warning_type"], w["warning_step"]) for w in bw if w["market"].startswith("KRW-") and w["market"][4:] in P)
    print(f"\nBithumb, последний снимок /market/virtual_asset_warning: {len(bw)} предупреждений, монет {len({w['market'] for w in bw})}")
    for k in sorted(bc):
        print(f"  {k[0]} {k[1]}: {bc[k]} (с перпом {bcp[k]})")
    ends = collections.Counter(w["end_date"] for w in bw)
    print("  концы (KST):", ends.most_common(4))
    print(f"Bithumb /market/all market_warning (유의): {sum(1 for m in ba if m.get('market_warning') not in (None, 'NONE'))}")
    # события записи
    E = list(csv.DictReader(open(OUT + "/events.csv")))
    ch = [e for e in E if e["action"] in ("on", "off", "change")]
    print(f"\nсобытий за запись (появление/снятие/смена): {len(ch)}")
    c2 = collections.Counter((e["source"], e["market"].split("-")[0], e["flag"], e["action"]) for e in ch)
    for k, v in sorted(c2.items()):
        print("  ", k, v)
    # сверка Upbit KRW с историей
    kr = [e for e in ch if e["source"] == "upbit" and e["market"].startswith("KRW-")]
    if kr:
        p = {"quoteCurrencyCode": "KRW", "start": t0.replace("T", " ").replace("Z", "")[:16] + ":00",
             "end": t1.replace("T", " ").replace("Z", "")[:16] + ":00", "page": 1, "size": 200}
        u = "https://crix-api-cdn.upbit.com/v1/crix/market-event-records?" + urllib.parse.urlencode(p)
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30).read())
        hist = d.get("list") or []
        print(f"\nсверка Upbit KRW: событий записи {len(kr)}, записей истории за то же время {d.get('totalCount')}")
        for e in kr:
            tm = datetime.strptime(e["time_utc"], "%Y-%m-%dT%H:%M:%SZ")
            near = [h for h in hist if h["code"].endswith(e["market"]) and h["eventType"] == e["flag"]]
            ok = any(abs((datetime.strptime(h["triggerTimeUtc" if e["action"] == "on" else "expirationTimeUtc"],
                                            "%Y-%m-%d %H:%M:%S") - tm).total_seconds()) <= 330 for h in near)
            print("  ", e["time_utc"], e["market"], e["flag"], e["action"], "в истории (±5,5 мин):", ok)
    # сверка Bithumb: закончившиеся за время записи
    bend = [e for e in ch if e["source"] == "bithumb_warn" and e["action"] == "off"]
    print(f"\nBithumb: снято за запись {len(bend)}")
    sym = {c["coinSymbol"]: c["coinType"] for c in json.load(open(OUT + "/web/bithumb_site/intro.json"))["data"]["coinList"]}
    code = {"PRICE_SUDDEN_FLUCTUATION": "01", "TRADING_VOLUME_SUDDEN_FLUCTUATION": "02",
            "DEPOSIT_AMOUNT_SUDDEN_FLUCTUATION": "03", "PRICE_DIFFERENCE_HIGH": "04",
            "SPECIFIC_ACCOUNT_HIGH_TRANSACTION": "05"}
    lvl = {"CAUTION": "1", "WARNING": "2", "DANGER": "3"}
    for e in bend[:20]:
        coin = e["market"].split("-")[1]
        ct = sym.get(coin)
        p = {"startDate": "2026-11-18", "endDate": "2026-11-21", "crncCd": "C0100", "coinType": ct,
             "warningType": code.get(e["flag"], ""), "warningLevel": lvl.get(e["step"], "1"), "size": 30}
        u = "https://gw.bithumb.com/exchange/v2/trade/virtual-asset/warning/history?" + urllib.parse.urlencode(p)
        try:
            d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (research-script/1.0)"}), timeout=30).read())
            items = (d.get("data") or {}).get("items") or []
        except Exception as ex:
            items = []
            print("  ошибка", ex)
        found = [i for i in items if i.get("endDateTime", "")[:16] == e["end_date"][:16]]
        print("  ", e["time_utc"], e["market"], e["flag"], e["step"], "конец", e["end_date"], "в истории:", bool(found),
              found[0]["startDateTime"] if found else "")
        time.sleep(1.2)


if __name__ == "__main__":
    main()
