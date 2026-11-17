"""Тест записи корейских сделок вокруг входов (scanner.kr_ticks_watch) и премий USDT (scanner.usdt_premium_watch) с подменой
Upbit, Bithumb, OKX, Binance и frankfurter.app. Запуск: python3 research/s97/rec_test.py из корня репозитория. Состояние
и файлы — во временной папке, сеть не нужна."""
import gzip
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
from datetime import datetime, timezone

TMP = tempfile.mkdtemp()
os.environ["STATE_FILE"] = os.path.join(TMP, "state.json")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner  # noqa: E402

DAY0 = 1_790_000_000 // 86400 * 86400
CLOCK = [DAY0]
time.time = lambda: CLOCK[0]
LOGS = []
scanner.log = lambda *a, **k: LOGS.append(" ".join(str(x) for x in a))
fails = []
CALLS = {"n": 0}
FAIL = {"ticks": False, "okx": False, "all": False}
STEP = 7                                           # сделка раз в 7 с на каждом рынке


def check(cond, what):
    print(("OK   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


def ticks_api(ex, q):
    """Модель /v1/trades/ticks: сутки биржи (Upbit — UTC, Bithumb — +9 ч), to — время суток, daysAgo, курсор."""
    sh = scanner.TK_TZ[ex]
    today = int((CLOCK[0] + sh) // 86400)
    day = today - int(q.get("daysAgo", 0))
    hh, mm, ss = map(int, q["to"].split(":"))
    end = day * 86400 - sh + hh * 3600 + mm * 60 + ss              # UTC-момент «to» в эти сутки
    start = day * 86400 - sh
    end = min(end, CLOCK[0])
    seq_end = int(q["cursor"]) if q.get("cursor") else None
    out = []
    t = (end - 1) // STEP * STEP
    while t >= start and len(out) < int(q["count"]):
        seq = t * 10
        if seq_end is None or seq < seq_end:
            out.append({"timestamp": t * 1000, "trade_price": 100.0 + t % 13, "trade_volume": 1.5,
                        "ask_bid": "BID" if (t // STEP) % 3 == 0 else "ASK", "sequential_id": seq})
        t -= STEP
    return out


def http(url, data=None, timeout=30):
    CALLS["n"] += 1
    if FAIL["all"]:
        raise urllib.error.URLError("нет сети")
    u = urllib.parse.urlsplit(url); q = dict(urllib.parse.parse_qsl(u.query))
    if "/v1/trades/ticks" in u.path:
        if FAIL["ticks"]:
            raise urllib.error.URLError("сбой")
        return json.dumps(ticks_api("upbit" if "upbit" in u.netloc else "bithumb", q))
    if "frankfurter" in u.netloc:
        return json.dumps({"date": "2026-09-21", "rates": {"CNY": 7.1, "TRY": 41.5, "KRW": 1390.0}})
    if "okx.com" in u.netloc:
        if FAIL["okx"]:
            raise urllib.error.URLError("сбой")
        return json.dumps({"data": {"sell": [{"price": p} for p in ("7.21", "7.20", "7.25", "7.22")]}})
    if "/v1/ticker" in u.path:
        return json.dumps([{"trade_price": 1405.0 if "upbit" in u.netloc else 1406.0}])
    raise AssertionError(url)


scanner.http = http
scanner.spot_json = lambda path, timeout=30: (None if FAIL["all"] else {"bidPrice": "41.9", "askPrice": "42.0"})
scanner._kr_list = lambda: {"upbit": {"AAA", "BBB"}, "bithumb": {"AAA", "CCC"}}
state = {}


def at(sec):
    CLOCK[0] = DAY0 + sec
    n0 = CALLS["n"]
    scanner.kr_ticks_watch(state)
    return CALLS["n"] - n0


# 1. входы: AAA (🔝) в 10:00 UTC, тот же AAA (👀) в 11:00 — окна сливаются; CCC (⏰) в 12:00 — только Bithumb (окно через
#    полночь Сеула, 15:00 UTC); монета 1000BBB (🇰🇷) — Upbit (без приставки)
state["virtual_KT"] = {"trades": [{"sym": "AAA", "opened": DAY0 + 10 * 3600}]}
state["virtual_RT"] = {"trades": [{"sym": "AAA", "opened": DAY0 + 11 * 3600}]}
state["virtual_O9"] = {"trades": [{"sym": "CCC", "opened": DAY0 + 12 * 3600}]}
state["virtual_KR"] = {"trades": [{"sym": "1000BBB", "opened": DAY0 + 12 * 3600}]}
n = at(11 * 3600 + 60)
jobs = state["tk"]["jobs"]
J = {(j["ex"], j["coin"]): j for j in jobs}
check(set(J) == {("upbit", "AAA"), ("bithumb", "AAA"), ("bithumb", "CCC"), ("upbit", "BBB")},
      f"задания по биржам с рынком монеты ({sorted(J)})")
check(J[("upbit", "AAA")]["a"] == DAY0 + 8 * 3600 and J[("upbit", "AAA")]["b"] == DAY0 + 17 * 3600,
      "окна AAA (🔝 10:00 и 👀 11:00) слились: 08:00–17:00")
check(n == 0, "до конца окна запросов нет")

# 2. конец окна + 5 мин: докачка частями (≤ 25 запросов за проход), пока все задания не закончатся
passes, maxreq = 0, 0
for k in range(200):
    r = at(18 * 3600 + 400 + k * 60)
    maxreq = max(maxreq, r); passes += 1
    if not state["tk"]["jobs"]:
        break
check(not state["tk"]["jobs"], f"все задания дописаны за {passes} проходов")
check(maxreq <= scanner.TK_BUDGET, f"за проход не больше {scanner.TK_BUDGET} запросов (было {maxreq})")


def read(ex, coin, a):
    fn = os.path.join(scanner.TK_DIR, datetime.fromtimestamp(a, timezone.utc).strftime("%Y-%m"), f"{ex}_{coin}_{a}.csv.gz")
    with gzip.open(fn, "rt") as f:
        return f.read().splitlines()


for (ex, coin), a, b in ((("upbit", "AAA"), DAY0 + 8 * 3600, DAY0 + 17 * 3600), (("bithumb", "CCC"), DAY0 + 10 * 3600, DAY0 + 18 * 3600),
                         (("bithumb", "AAA"), DAY0 + 8 * 3600, DAY0 + 17 * 3600), (("upbit", "BBB"), DAY0 + 10 * 3600, DAY0 + 18 * 3600)):
    L = read(ex, coin, a)
    ts = [int(r.split(",")[0]) for r in L[1:]]
    want = [t * 1000 for t in range((a + STEP - 1) // STEP * STEP, b + 1, STEP)]
    check(L[0] == "ts_ms,price,volume,side" and ts == want,
          f"{ex} {coin}: все сделки окна по возрастанию, без пропусков и дублей ({len(ts)} из {len(want)})")
L = read("bithumb", "CCC", DAY0 + 10 * 3600)
sides = {r.split(",")[3] for r in L[1:]}
check(sides == {"A", "B"}, "сторона тейкера записана (A и B)")
check(not os.listdir(os.path.join(scanner.TK_DIR, "tmp")), "временные файлы удалены")

# 3. сбой бирж: задание остаётся и продолжается позже; старое окно (> 6,5 сут) бросается
state["virtual_KT"]["trades"].append({"sym": "AAA", "opened": DAY0 + 2 * 86400})
FAIL["ticks"] = True
at(2 * 86400 + 7 * 3600)
check(len(state["tk"]["jobs"]) == 2 and all(j["fail"] >= 1 for j in state["tk"]["jobs"]), "сбой — задания живы, повтор позже")
FAIL["ticks"] = False
for k in range(100):
    at(2 * 86400 + 7 * 3600 + 60 * (k + 1))
    if not state["tk"]["jobs"]:
        break
check(not state["tk"]["jobs"], "после сбоя задания дописаны")
state["virtual_KT"]["trades"].append({"sym": "AAA", "opened": DAY0 + 3 * 86400})
FAIL["ticks"] = True
at(3 * 86400 + 7 * 3600)
FAIL["ticks"] = False
at(10 * 86400)
check(not state["tk"]["jobs"] and any("запись брошена" in x for x in LOGS), "окно старше 6,5 суток — брошено с записью в журнал")

# 4. премии USDT
st = {}
CLOCK[0] = DAY0 + 600
scanner.usdt_premium_watch(st)
fn = os.path.join(scanner.PR_DIR, datetime.fromtimestamp(CLOCK[0], timezone.utc).strftime("%Y-%m") + ".csv")
L = open(fn).read().splitlines()
check(L[0].startswith("ts,cny_okx_best") and len(L) == 2, "премии: заголовок и первая строка")
row = dict(zip(L[0].split(","), L[1].split(",")))
check(row["cny_okx_best"] == "7.2" and row["cny_okx_med10"] == "7.22" and row["try_ask"] == "42" and row["krw_upbit"] == "1405"
      and row["usd_krw"] == "1390", f"премии: значения верны ({row})")
CLOCK[0] += 300; scanner.usdt_premium_watch(st)
check(len(open(fn).read().splitlines()) == 2, "через 5 мин — без новой строки")
FAIL["okx"] = True; CLOCK[0] += 400; scanner.usdt_premium_watch(st)
L = open(fn).read().splitlines(); row = dict(zip(L[0].split(","), L[-1].split(",")))
check(len(L) == 3 and row["cny_okx_best"] == "" and row["try_bid"] == "41.9", "OKX не ответил — пустое поле, остальные записаны")
FAIL["all"] = True; CLOCK[0] += 700; scanner.usdt_premium_watch(st)
check(len(open(fn).read().splitlines()) == 3 and any("ПРЕМИЯ" in x for x in LOGS), "всё упало — строки нет, запись в журнал")

print("\nИтог:", "все проверки прошли" if not fails else f"не прошло {len(fails)}: " + "; ".join(fails))
sys.exit(1 if fails else 0)
