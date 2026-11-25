"""s286 — загрузка календарей запланированных событий (изучение; доходы не считаются).

Всё без ключей, User-Agent research-script/1.0, сырьё — в /dev/shm/s286/raw (диск почти полон).
Запуск: python3 -I fetch_calendars.py [часть ...]; части: ziplime xoomar ff fed ecb boj sec binance
  ziplime — официальные выпуски BLS/BEA/Census/DOL с меткой эмбарго из текста выпуска (Hugging Face
            ZipLime/us-economic-events, таблица releases, через datasets-server — JSON без parquet);
  xoomar  — расписание выпусков BLS/BEA/Census и решений ФРС с 01.2021 (XOOMAR/us-economic-release-calendar);
  ff      — архив календаря Forex Factory 2007 – 07.04.2025 (Ehsanrs2/Forex_Factory_Calendar, время — Тегеран);
  fed     — страницы ФРС с календарями FOMC (2020 — история, 2021+ — текущая страница);
  ecb     — список решений ЕЦБ по ставкам;
  boj     — списки решений Банка Японии по годам;
  sec     — подачи EDGAR (data.sec.gov/submissions) MSTR, COIN, HOOD и майнеров — время отчётностей (8-K, п. 2.02);
  binance — список поставочных фьючерсов USDT-M в архиве data.binance.vision (даты поставки)."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "research-script/1.0"}
RAW = "/dev/shm/s286/raw"
os.makedirs(RAW, exist_ok=True)


def get(url, tries=5, raw=False, timeout=60):
    err = None
    for k in range(tries):
        try:
            b = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()
            return b if raw else json.loads(b)
        except Exception as e:  # сеть ненадёжна — пауза и повтор
            err = e
            time.sleep(2 * (k + 1))
    raise RuntimeError(f"{url}: {err}")


def ziplime():
    out = {}
    for cfg in ("releases", "calendar"):
        rows, off = [], 0
        while True:
            u = ("https://datasets-server.huggingface.co/rows?dataset=ZipLime/us-economic-events"
                 f"&config={cfg}&split=train&offset={off}&length=100")
            d = get(u)
            rows += [r["row"] for r in d["rows"]]
            off += 100
            if off >= d["num_rows_total"]:
                break
            time.sleep(0.3)
        out[cfg] = rows
        print(cfg, len(rows), flush=True)
    json.dump(out, open(f"{RAW}/ziplime.json", "w"))


def xoomar():
    b = get("https://huggingface.co/datasets/XOOMAR/us-economic-release-calendar/resolve/main/"
            "us-economic-release-calendar.csv", raw=True)
    open(f"{RAW}/xoomar.csv", "wb").write(b)
    print("xoomar", len(b))


def ff():
    b = get("https://huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar/resolve/main/forex_factory_cache.csv",
            raw=True, timeout=300)
    open(f"{RAW}/ff.csv", "wb").write(b)
    print("ff", len(b))


def fed():
    for name, u in [("fomc_2020.html", "https://www.federalreserve.gov/monetarypolicy/fomchistorical2020.htm"),
                    ("fomc_cur.html", "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm")]:
        b = get(u, raw=True)
        open(f"{RAW}/{name}", "wb").write(b)
        print(name, len(b))


def ecb():
    b = get("https://www.ecb.europa.eu/press/govcdec/mopo/html/index.en.html", raw=True)
    open(f"{RAW}/ecb_mopo.html", "wb").write(b)
    print("ecb", len(b))


def boj():
    for y in range(2020, 2027):
        u = f"https://www.boj.or.jp/en/mopo/mpmdeci/state_{y}/index.htm"
        try:
            b = get(u, raw=True, tries=3)
        except RuntimeError as e:
            print("boj", y, e)
            continue
        open(f"{RAW}/boj_{y}.html", "wb").write(b)
        print("boj", y, len(b))
        time.sleep(1)
    b = get("https://www.boj.or.jp/en/mopo/mpmdeci/index.htm", raw=True)
    open(f"{RAW}/boj_index.html", "wb").write(b)


# CIK компаний «прокси-крипты» (EDGAR): Strategy (MSTR), Coinbase, Robinhood, майнеры
SEC = {"MSTR": 1050446, "COIN": 1679788, "HOOD": 1783879, "MARA": 1507605, "RIOT": 1167419, "CLSK": 827876,
       "HUT": 1964789, "CORZ": 1839341, "IREN": 1878848, "CIFR": 1819989, "BITF": 1858293}


def sec():
    os.makedirs(f"{RAW}/sec", exist_ok=True)
    for tk, cik in SEC.items():
        u = f"https://data.sec.gov/submissions/CIK{cik:010d}.json"
        try:
            d = get(u, tries=3)
        except RuntimeError as e:
            print("sec", tk, e)
            continue
        files = d.get("filings", {}).get("files", [])
        json.dump(d, open(f"{RAW}/sec/{tk}.json", "w"))
        for f in files:  # старые подачи — отдельными файлами
            try:
                dd = get("https://data.sec.gov/submissions/" + f["name"], tries=3)
                json.dump(dd, open(f"{RAW}/sec/{tk}_{f['name']}", "w"))
            except RuntimeError as e:
                print("sec", tk, f["name"], e)
            time.sleep(0.3)
        print("sec", tk, d.get("name"), len(d["filings"]["recent"]["form"]), "файлов", len(files), flush=True)
        time.sleep(0.5)


def binance():
    """Поставочные фьючерсы USDT-M (BTCUSDT_YYMMDD и др.) из S3-листинга архива: префиксы monthly/klines/."""
    base = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
    names, marker = [], ""
    while True:
        u = f"{base}?delimiter=/&prefix=data/futures/um/monthly/klines/" + (
            f"&marker={urllib.parse.quote(marker)}" if marker else "")
        b = get(u, raw=True).decode()
        import re
        pre = re.findall(r"<Prefix>data/futures/um/monthly/klines/([^<]+)/</Prefix>", b)
        names += pre
        trunc = "<IsTruncated>true</IsTruncated>" in b
        nm = re.findall(r"<NextMarker>([^<]+)</NextMarker>", b)
        if not trunc:
            break
        marker = nm[0] if nm else "data/futures/um/monthly/klines/" + pre[-1] + "/"
        time.sleep(0.3)
    dl = sorted(n for n in names if "_" in n)
    json.dump(dl, open(f"{RAW}/binance_delivery.json", "w"))
    print("binance символов", len(names), "поставочных", len(dl), dl[:5], dl[-5:])


if __name__ == "__main__":
    parts = sys.argv[1:] or ["ziplime", "xoomar", "ff", "fed", "ecb", "boj", "sec", "binance"]
    for p in parts:
        globals()[p]()
