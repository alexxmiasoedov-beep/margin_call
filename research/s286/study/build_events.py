"""s286 — единая таблица запланированных событий вне крипты и крипто-календаря с точным временем (UTC).

Источники (сырьё — /dev/shm/s286/raw, см. fetch_calendars.py):
- макро США — ZipLime/us-economic-events (метка эмбарго из текста выпуска BLS/BEA/Census/DOL);
- ISM — даты Forex Factory (архив до 07.04.2025), дальше правило «1-й (услуги — 3-й) рабочий день, 10:00 ET»;
- FOMC (решение 14:00 ET, пресс-конференция 14:30 ET, протокол 14:00 ET) — страницы ФРС;
- ЕЦБ — список решений (13:45 / 14:15 CET, пресс-конференция 14:30 / 14:45 CET; смена с 21.07.2022);
- Банк Японии — даты со страниц BoJ, время — Forex Factory (фактическое, где записано), иначе «≈ 03:00 UTC» (флаг approx);
- PMI Китая (NBS) — Forex Factory до 03.2025 (время есть), 2025–2026 — календари NBS, 09:30 по Пекину;
- открытие и закрытие NYSE (праздники и короткие дни — списком), окно фиксинга ETF 15:00–16:00 ET (с 11.01.2024);
- экспирации опционов США (3-я пятница; квартальная — «тройной ведьмин день»), еженедельные опционы IBIT (с 19.11.2024);
- Deribit 08:00 UTC (s157/expiries.json: D/W/M/Q и OI на экспирации, по 18.11.2026), поставка квартальных Binance;
- CME: экспирация месячных BTC (последняя пятница, BRR 15:00–16:00 Лондон, правило переноса), закрытие на выходные
  (пт 16:00 CT) и открытие (вс 17:00 CT) — до перехода на 24/7 29.05.2026;
- отчётности MSTR, COIN, HOOD и майнеров (8-K, п. 2.02, время приёма EDGAR), понедельничные 8-K Strategy о покупке BTC.
Выход — /home/user/mc_data/s286/events.csv (fam, t — UTC, с; tz — местная зона события; tier; note).
Запуск: python3 -I build_events.py"""
import calendar
import collections
import datetime as dt
import glob
import json
import os
import re
from zoneinfo import ZoneInfo

import pandas as pd

RAW = "/dev/shm/s286/raw"
OUT = "/home/user/mc_data/s286"
os.makedirs(OUT, exist_ok=True)
T0, T1 = dt.datetime(2020, 9, 1, tzinfo=dt.UTC), dt.datetime(2026, 11, 25, tzinfo=dt.UTC)
NY, LDN, CT, FRA, TYO = (ZoneInfo(z) for z in ("America/New_York", "Europe/London", "America/Chicago",
                                               "Europe/Berlin", "Asia/Tokyo"))
EV = []


def add(fam, t, tz, tier, note="", src=""):
    t = t.astimezone(dt.UTC)
    if T0 <= t < T1:
        EV.append(dict(fam=fam, t=int(t.timestamp()), utc=t.strftime("%Y-%m-%d %H:%M"), tz=tz, tier=tier, note=note,
                       src=src))


def loc(d, hh, mm, tz):
    return dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=tz)


# ---------- календари рабочих дней ----------
NYSE_HOL = {  # полные закрытия NYSE 2020-09 … 2026-12
    "2020-09-07", "2020-11-26", "2020-12-25",
    "2021-01-01", "2021-01-18", "2021-02-15", "2021-04-02", "2021-05-31", "2021-07-05", "2021-09-06", "2021-11-25",
    "2021-12-24",
    "2022-01-17", "2022-02-21", "2022-04-15", "2022-05-30", "2022-06-20", "2022-07-04", "2022-09-05", "2022-11-24",
    "2022-12-26",
    "2023-01-02", "2023-01-16", "2023-02-20", "2023-04-07", "2023-05-29", "2023-06-19", "2023-07-04", "2023-09-04",
    "2023-11-23", "2023-12-25",
    "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04", "2024-09-02",
    "2024-11-28", "2024-12-25",
    "2025-01-01", "2025-01-09", "2025-01-20", "2025-02-17", "2025-04-18", "2025-05-26", "2025-06-19", "2025-07-04",
    "2025-09-01", "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
    "2026-11-26", "2026-12-25"}
NYSE_EARLY = {"2020-11-27", "2020-12-24", "2021-11-26", "2022-11-25", "2023-07-03", "2023-11-24", "2024-07-03",
              "2024-11-29", "2024-12-24", "2025-07-03", "2025-11-28", "2025-12-24", "2026-11-27", "2026-12-24"}
UK_HOL = {  # банковские праздники Англии (для правила экспирации CME)
    "2020-12-25", "2020-12-28", "2021-01-01", "2021-04-02", "2021-04-05", "2021-05-03", "2021-05-31", "2021-08-30",
    "2021-12-27", "2021-12-28", "2022-01-03", "2022-04-15", "2022-04-18", "2022-05-02", "2022-06-02", "2022-06-03",
    "2022-08-29", "2022-09-19", "2022-12-26", "2022-12-27", "2023-01-02", "2023-04-07", "2023-04-10", "2023-05-01",
    "2023-05-08", "2023-05-29", "2023-08-28", "2023-12-25", "2023-12-26", "2024-01-01", "2024-03-29", "2024-04-01",
    "2024-05-06", "2024-05-27", "2024-08-26", "2024-12-25", "2024-12-26", "2025-01-01", "2025-04-18", "2025-04-21",
    "2025-05-05", "2025-05-26", "2025-08-25", "2025-12-25", "2025-12-26", "2026-01-01", "2026-04-03", "2026-04-06",
    "2026-05-04", "2026-05-25", "2026-08-31", "2026-12-25", "2026-12-28"}
US_FED_HOL = {  # федеральные праздники (для правила ISM и CME)
    "2020-09-07", "2020-10-12", "2020-11-11", "2020-11-26", "2020-12-25", "2021-01-01", "2021-01-18", "2021-02-15",
    "2021-05-31", "2021-06-18", "2021-07-05", "2021-09-06", "2021-10-11", "2021-11-11", "2021-11-25", "2021-12-24",
    "2021-12-31", "2022-01-17", "2022-02-21", "2022-05-30", "2022-06-20", "2022-07-04", "2022-09-05", "2022-10-10",
    "2022-11-11", "2022-11-24", "2022-12-26", "2023-01-02", "2023-01-16", "2023-02-20", "2023-05-29", "2023-06-19",
    "2023-07-04", "2023-09-04", "2023-10-09", "2023-11-10", "2023-11-23", "2023-12-25", "2024-01-01", "2024-01-15",
    "2024-02-19", "2024-05-27", "2024-06-19", "2024-07-04", "2024-09-02", "2024-10-14", "2024-11-11", "2024-11-28",
    "2024-12-25", "2025-01-01", "2025-01-20", "2025-02-17", "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01",
    "2025-10-13", "2025-11-11", "2025-11-27", "2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-10-12", "2026-11-11", "2026-11-26", "2026-12-25"}


def days(a=dt.date(2020, 9, 1), b=dt.date(2026, 11, 25)):
    d = a
    while d < b:
        yield d
        d += dt.timedelta(days=1)


def nyse_day(d):
    return d.weekday() < 5 and d.isoformat() not in NYSE_HOL


def us_bday(d):
    return d.weekday() < 5 and d.isoformat() not in US_FED_HOL


def third_friday(y, m):
    c = [d for d in (dt.date(y, m, k) for k in range(15, 22)) if d.weekday() == 4]
    return c[0]


def last_friday(y, m):
    k = calendar.monthrange(y, m)[1]
    d = dt.date(y, m, k)
    while d.weekday() != 4:
        d -= dt.timedelta(days=1)
    return d


# ---------- макро США (ZipLime) ----------
ZMAP = {"CPI": ("CPI", 1), "EMPLOYMENT": ("NFP", 1), "PPI": ("PPI", 2), "PERSONAL_INCOME": ("PCE", 2),
        "RETAIL_SALES": ("RETAIL", 2), "GDP": ("GDP", 2), "JOLTS": ("JOLTS", 2), "JOBLESS_CLAIMS": ("CLAIMS", 3),
        "DURABLE_GOODS": ("DURABLE", 3), "HOUSING": ("HOUSING", 3), "NEW_HOME_SALES": ("NHS", 3), "TRADE": ("TRADE", 3)}


def us_macro():
    z = json.load(open(f"{RAW}/ziplime.json"))["releases"]
    for r in z:
        fam, tier = ZMAP[r["release_family"]]
        t = dt.datetime.fromisoformat(r["release_at"].replace("Z", "+00:00"))
        if fam == "GDP" and r.get("estimate_stage") not in ("advance", None):
            fam, tier = "GDP23", 3            # вторая и третья оценки ВВП — слабее «авансовой»
        add(fam, t, "America/New_York", tier, r["release_id"], "ziplime")


# ---------- Forex Factory: время по Тегерану ----------
def ff_load():
    f = pd.read_csv(f"{RAW}/ff.csv", usecols=["DateTime", "Currency", "Impact", "Event"])
    f = f[f.DateTime >= "2020-08-25"].copy()
    loc_t = pd.to_datetime(f.DateTime.str[:19])
    off = f.DateTime.str[-6:]
    # В выгрузке смещение +04:30 стоит и после отмены летнего времени в Иране (с 22.03.2023 — всегда +03:30)
    fix = (loc_t >= "2023-03-22") & (off == "+04:30")
    hours = off.str[1:3].astype(int) + off.str[4:6].astype(int) / 60
    hours = hours.where(~fix, 3.5)
    f["utc"] = (loc_t - pd.to_timedelta(hours, unit="h")).dt.tz_localize("UTC")
    f["notime"] = f.DateTime.str[11:16].isin(["00:00", "23:59"])
    f["date_loc"] = loc_t.dt.date
    return f


def ism(ff):
    seen = set()
    for ev, fam in (("ISM Manufacturing PMI", "ISM_M"), ("ISM Services PMI", "ISM_S")):
        x = ff[(ff.Currency == "USD") & (ff.Event == ev)]
        for _, r in x.iterrows():
            # без времени (00:00) запись стоит на дату выпуска по Тегерану — она совпадает с датой выпуска в США
            d = r.date_loc if r.notime else r.utc.tz_convert(NY).date()
            add(fam, loc(d, 10, 0, NY), "America/New_York", 2 if fam == "ISM_M" else 3, ev, "ff")
            seen.add((fam, d.year, d.month))
    # после архива Forex Factory — правило: 1-й (производство) и 3-й (услуги) рабочий день месяца, 10:00 ET
    for y in (2025, 2026):
        for m in range(1, 13):
            bd = [d for d in (dt.date(y, m, k) for k in range(1, 10)) if us_bday(d)]
            for fam, k in (("ISM_M", 0), ("ISM_S", 2)):
                if (fam, y, m) not in seen and dt.date(y, m, 1) >= dt.date(2025, 4, 8):
                    add(fam, loc(bd[k], 10, 0, NY), "America/New_York", 2 if fam == "ISM_M" else 3, "rule", "rule")


# ---------- FOMC ----------
def fomc():
    stm, pc, minutes = set(), set(), set()
    for fn in ("fomc_2020.html", "fomc_cur.html"):
        h = open(f"{RAW}/{fn}", encoding="utf-8", errors="ignore").read()
        stm |= set(re.findall(r"monetary(\d{8})a\.htm", h))
        pc |= set(re.findall(r"fomcpresconf(\d{8})\.htm", h))
        for mth, dd, yy in re.findall(r"\(Released (\w+) (\d{1,2}), (\d{4})\)", h):
            minutes.add(dt.datetime.strptime(f"{mth} {dd} {yy}", "%B %d %Y").strftime("%Y%m%d"))
    xo = pd.read_csv(f"{RAW}/xoomar.csv")
    for _, r in xo[xo.source == "fed"].iterrows():
        d = r.scheduled_at[:10].replace("-", "")
        if r.event_name == "FOMC Rate Decision":
            stm.add(d)
        elif r.event_name == "FOMC Minutes":
            minutes.add(d)
    for d in sorted(stm):
        dd = dt.date(int(d[:4]), int(d[4:6]), int(d[6:]))
        if dd.weekday() >= 5:
            continue
        add("FOMC", loc(dd, 14, 0, NY), "America/New_York", 1, "statement", "fed")
        if d in pc or dd >= dt.date(2019, 1, 1):
            add("FOMC_PC", loc(dd, 14, 30, NY), "America/New_York", 1, "press conference", "fed")
    for d in sorted(minutes):
        dd = dt.date(int(d[:4]), int(d[4:6]), int(d[6:]))
        add("FOMC_MIN", loc(dd, 14, 0, NY), "America/New_York", 2, "minutes", "fed")


# ---------- ЕЦБ ----------
def ecb():
    for fn in sorted(glob.glob(f"{RAW}/ecb_20*.html")):
        h = open(fn, encoding="utf-8", errors="ignore").read()
        for d, href in re.findall(r'<dt isoDate="(\d{4}-\d{2}-\d{2})">.*?<a href="([^"]+)"', h, re.S):
            if "ecb.mp" not in href:
                continue
            dd = dt.date.fromisoformat(d)
            new = dd >= dt.date(2022, 7, 21)
            add("ECB", loc(dd, 14, 15, FRA) if new else loc(dd, 13, 45, FRA), "Europe/Berlin", 2, "decision", "ecb")
            add("ECB_PC", loc(dd, 14, 45, FRA) if new else loc(dd, 14, 30, FRA), "Europe/Berlin", 2, "press", "ecb")


# ---------- Банк Японии ----------
def boj(ff):
    dates = set()
    for fn in glob.glob(f"{RAW}/boj_20*.html"):
        h = open(fn, encoding="utf-8", errors="ignore").read()
        dates |= {dt.date(2000 + int(a), int(b), int(c)) for a, b, c in
                  re.findall(r"state_\d{4}/k(\d{2})(\d{2})(\d{2})a\.htm", h)}
    x = ff[(ff.Currency == "JPY") & ff.Event.isin(["Monetary Policy Statement", "BOJ Policy Rate"])]
    known = {}
    for _, r in x.iterrows():
        if r.notime:
            dates.add(r.date_loc)
            continue
        d = r.utc.tz_convert(TYO).date()
        dates.add(d)
        known[d] = min(known.get(d, r.utc), r.utc)
    for d in sorted(dates):
        if d in known:
            add("BOJ", known[d].to_pydatetime(), "Asia/Tokyo", 2, "statement (FF time)", "boj+ff")
        else:
            add("BOJ_APPROX", loc(d, 12, 0, TYO), "Asia/Tokyo", 2, "statement time unknown, ~12:00 JST", "boj")


# ---------- PMI Китая ----------
NBS_PMI = ["2025-01-27", "2025-03-01", "2025-03-31", "2025-04-30", "2025-05-31", "2025-06-30", "2025-07-31",
           "2025-08-31", "2025-09-30", "2025-10-31", "2025-11-30", "2025-12-31", "2026-01-31", "2026-03-04",
           "2026-03-31", "2026-04-30", "2026-05-31", "2026-06-30", "2026-07-31", "2026-08-31", "2026-09-30",
           "2026-10-31"]


def cn_pmi(ff):
    SH = ZoneInfo("Asia/Shanghai")
    x = ff[(ff.Currency == "CNY") & (ff.Event == "Manufacturing PMI")]
    seen = set()
    for _, r in x.iterrows():
        if r.notime:
            t = loc(r.date_loc, 9, 30, SH)
        else:
            t = r.utc.to_pydatetime()
            hm = t.astimezone(SH).strftime("%H:%M")
            if hm not in ("09:00", "09:30"):      # сбой времени в выгрузке (28.02.2021: 15:05) — по правилу NBS
                mm = 0 if t < dt.datetime(2021, 3, 1, tzinfo=dt.UTC) else 30
                t = loc(t.astimezone(SH).date(), 9, mm, SH)
        if t.date() >= dt.date(2025, 1, 1):
            continue
        add("CN_PMI", t, "Asia/Shanghai", 3, "NBS PMI", "ff")
        seen.add(t.astimezone(SH).date())
    for d in NBS_PMI:
        add("CN_PMI", loc(dt.date.fromisoformat(d), 9, 30, SH), "Asia/Shanghai", 3, "NBS PMI", "nbs")


# ---------- биржи США ----------
def us_equity():
    for d in days():
        if not nyse_day(d):
            continue
        add("US_OPEN", loc(d, 9, 30, NY), "America/New_York", 3, "NYSE open")
        add("US_10", loc(d, 10, 0, NY), "America/New_York", 3, "10:00 ET")
        early = d.isoformat() in NYSE_EARLY
        add("US_CLOSE", loc(d, 13, 0, NY) if early else loc(d, 16, 0, NY), "America/New_York", 3,
            "early close" if early else "NYSE close")
        if d >= dt.date(2024, 1, 11) and not early:
            add("ETF_FIX", loc(d, 15, 0, NY), "America/New_York", 3, "BRRNY window 15:00-16:00 ET (start)")
    for y in range(2020, 2027):
        for m in range(1, 13):
            d = third_friday(y, m)
            q = m in (3, 6, 9, 12)
            add("OPEX_Q" if q else "OPEX_M", loc(d, 16, 0, NY), "America/New_York", 3,
                "triple witching + S&P/Nasdaq rebalance" if q else "monthly OPEX")
            add("OPEX_SOQ", loc(d, 9, 30, NY), "America/New_York", 3, "SPX AM settlement (SOQ)")
    for d in days(dt.date(2024, 11, 22)):
        if d.weekday() == 4 and nyse_day(d) and d != third_friday(d.year, d.month):
            add("IBIT_W", loc(d, 16, 0, NY), "America/New_York", 3, "IBIT weekly options expiry")
    # псевдособытия для сравнений «до / после» (не события, а те же часы во все дни)
    for d in days():
        if nyse_day(d):
            add("NY1500", loc(d, 15, 0, NY), "America/New_York", 9, "15:00 ET every NYSE day (ETF window before/after)")
            if d.weekday() == 4:
                add("FRI_1600", loc(d, 16, 0, NY), "America/New_York", 9, "Friday 16:00 ET (IBIT options before/after)")


# ---------- экспирации крипто ----------
def deribit():
    for x in json.load(open("/home/user/mc_data/s157/expiries.json")):
        if x["cur"] != "BTC":
            continue
        t = dt.datetime.fromisoformat(x["t"]).replace(second=0, microsecond=0)
        add("DRB_" + x["type"], t, "UTC", 3 if x["type"] in ("D", "W") else 2,
            f"{x['exp']} OI ${x['notional'] / 1e9:.2f}B maxpain {x['maxpain']}", "s157")


def binance_delivery():
    for s in json.load(open(f"{RAW}/binance_delivery.json")):
        m = re.match(r"BTCUSDT_(\d{2})(\d{2})(\d{2})$", s)
        if m:
            d = dt.date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
            add("BN_DELIV", loc(d, 8, 0, dt.UTC), "UTC", 2, s, "binance")


def cme():
    for y in range(2020, 2027):
        for m in range(1, 13):
            d = last_friday(y, m)
            while d.isoformat() in UK_HOL or d.isoformat() in US_FED_HOL or d.weekday() >= 5:
                d -= dt.timedelta(days=1)
            add("CME_EXP", loc(d, 15, 0, LDN), "Europe/London", 2, "BRR window 15:00-16:00 London (start)")
    cut = dt.date(2026, 5, 29)                   # с 29.05.2026 CME торгует крипту 24/7
    for d in days():
        if d >= cut:
            break
        if d.weekday() == 4:
            add("CME_CLOSE", loc(d, 16, 0, CT), "America/Chicago", 3, "weekend close")
        if d.weekday() == 6:
            add("CME_OPEN", loc(d, 17, 0, CT), "America/Chicago", 3, "Sunday reopen")
    for d in days(cut):
        if d.weekday() == 6:                     # CME уже 24/7 — те же часы воскресенья без открытия
            add("CME_OPEN_247", loc(d, 17, 0, CT), "America/Chicago", 9, "Sunday 17:00 CT after 24/7 launch")


# ---------- отчётности и 8-K Strategy ----------
def sec():
    for fn in glob.glob(f"{RAW}/sec/*.json"):
        tk = os.path.basename(fn).split("_")[0].split(".")[0]
        d = json.load(open(fn))
        r = d["filings"]["recent"] if "filings" in d else d
        for form, acc, items in zip(r["form"], r["acceptanceDateTime"], r["items"]):
            if form != "8-K":
                continue
            t = dt.datetime.fromisoformat(acc.replace("Z", "+00:00"))
            its = set(items.split(","))
            if "2.02" in its:
                add("EARN_" + ("MINER" if tk not in ("MSTR", "COIN", "HOOD") else tk), t, "America/New_York", 3,
                    f"{tk} 8-K 2.02", "sec")
            elif tk == "MSTR" and "8.01" in its and t.astimezone(NY).weekday() == 0 and t.astimezone(NY).hour < 9:
                add("MSTR_BUY", t, "America/New_York", 3, "Strategy Monday 8-K (BTC purchases)", "sec")


def main():
    ff = ff_load()
    us_macro(); ism(ff); fomc(); ecb(); boj(ff); cn_pmi(ff); us_equity(); deribit(); binance_delivery(); cme(); sec()
    e = pd.DataFrame(EV).drop_duplicates(["fam", "t"]).sort_values(["t", "fam"])
    e.to_csv(f"{OUT}/events.csv", index=False)
    per = [("2020–2022", "2020-10-01", "2022-10-01"), ("2022–2024", "2022-10-01", "2024-10-01"),
           ("2024–2026", "2024-10-01", "2026-10-19")]
    rows = []
    for fam, g in e.groupby("fam"):
        r = {"fam": fam, "tier": g.tier.iloc[0], "всего": len(g), "с": g.utc.min()[:10], "по": g.utc.max()[:10]}
        for p, a, b in per:
            n = ((g.utc >= a) & (g.utc < b)).sum()
            mo = (pd.Timestamp(b) - pd.Timestamp(a)).days / 30.44
            r[p] = round(n / mo, 2)
        rows.append(r)
    s = pd.DataFrame(rows).sort_values(["tier", "fam"])
    s.to_csv(f"{OUT}/event_counts.csv", index=False)
    print(s.to_string(index=False))
    # проверка: местное время событий одной семьи (сколько разных «часов:минут»)
    e["loc"] = [pd.Timestamp(t, unit="s", tz="UTC").tz_convert(z).strftime("%H:%M") if z != "UTC" else
                pd.Timestamp(t, unit="s", tz="UTC").strftime("%H:%M") for t, z in zip(e.t, e.tz)]
    chk = e.groupby("fam")["loc"].agg(lambda s: dict(collections.Counter(s).most_common(3)))
    print(chk.to_string())


if __name__ == "__main__":
    main()
