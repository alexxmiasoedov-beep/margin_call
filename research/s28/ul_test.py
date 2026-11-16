"""s28 — Тест журнала 🔓 (scanner.unlock_rule) с подменой ответов CoinMarketCap и Binance: расписание по проходам, группа
событий, сверка цены, опоздание, сбои CMC, устаревшее расписание, повтор обновления без повторного входа, выход по
времени через сутки после разлока."""
import json
import os
import sys
import tempfile

os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
os.environ["POSITION_USDT"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner, trader  # noqa: E402

D = 86400
T0 = 1795000000.0                       # «сейчас» в начале теста
CLOCK = [T0]
scanner.time.time = lambda: CLOCK[0]
trader.time.time = lambda: CLOCK[0]
LOG = []
scanner.log = lambda *a: LOG.append(" ".join(str(x) for x in a))
trader.log = lambda *a: LOG.append(" ".join(str(x) for x in a))


def iso(t):
    from datetime import datetime, timezone
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


T1 = T0 + 8 * D + 3600                  # AAA: cliff 10% через 8 сут
T2 = T0 + 9.5 * D                       # 1000BBB: linear 30% через 9,5 сут
T3 = T0 + 8 * D + 7200                  # DDD: cliff 8%, но цена фьючерса не та
T4 = T0 + 5 * D                         # GGG: cliff 6% через 5 сут — срок входа уже прошёл
CIRC = 1e9
EV = {
    1: ([(T1 - D, 1e6, "linear", "Ecosystem")] + [(T1, 1e8, "cliff", "Investors"), (T1 + 1.5 * D, 5e6, "linear", "Team")]
        + [(T0 + k * D, 1e6, "linear", "Ecosystem") for k in range(1, 7)]),
    2: [(T2, 3e8, "linear", "Community")],
    4: [(T3, 8e7, "cliff", "Team")],
    5: [(T0 + 3 * D, 1e6, "linear", "Ecosystem")],
    6: [(T4, 6e7, "cliff", "Advisors")],
    7: [(T0 + 8 * D, 4e7, "cliff", "Team"), (T0 + 9 * D + 2 * D + 1, 2e8, "linear", "Community")],   # 4% и 20% — мимо
}
LISTING = [
    {"cryptoId": 1, "symbol": "AAA", "circulatingSupply": CIRC, "quotes": [{"price": 1.0}]},
    {"cryptoId": 2, "symbol": "BBB", "circulatingSupply": CIRC, "quotes": [{"price": 2e-5}]},
    {"cryptoId": 3, "symbol": "CCC", "circulatingSupply": CIRC, "quotes": [{"price": 1.0}]},     # нет фьючерса
    {"cryptoId": 4, "symbol": "DDD", "circulatingSupply": CIRC, "quotes": [{"price": 1.0}]},
    {"cryptoId": 5, "symbol": "USDC", "circulatingSupply": CIRC, "quotes": [{"price": 1.0}]},    # стейблкоин
    {"cryptoId": 6, "symbol": "GGG", "circulatingSupply": CIRC, "quotes": [{"price": 1.0}]},
    {"cryptoId": 7, "symbol": "HHH", "circulatingSupply": CIRC, "quotes": [{"price": 1.0}]},
    {"cryptoId": 8, "symbol": "FFF", "circulatingSupply": CIRC, "quotes": [{"price": 1.0}]},     # расписание не отдаётся
]
FAIL = {"listing": False, "events": False}
CALLS = {"listing": 0, "event": 0}
MARK = {"AAA": 1.0, "1000BBB": 0.02, "DDD": 0.1, "GGG": 1.0, "HHH": 1.0, "FFF": 1.0, "USDC": 1.0, "BTC": 90000.0}


def fake_http_json(url, timeout=30):
    if "/token-unlock/listing" in url:
        CALLS["listing"] += 1
        if FAIL["listing"]:
            return None
        page = int(url.split("start=")[1].split("&")[0])
        full = LISTING + [{"cryptoId": 1000 + i, "symbol": f"ZZ{i}", "circulatingSupply": CIRC, "quotes": [{"price": 1.0}]}
                          for i in range(150)]                       # без фьючерсов — чтобы страниц было две
        rows = full[(page - 1) * 100: page * 100]
        return {"data": {"tokenUnlockList": rows, "totalCount": str(len(full))}, "status": {}}
    if "/token-unlock/event" in url:
        CALLS["event"] += 1
        cid = int(url.split("cryptoId=")[1].split("&")[0])
        if FAIL["events"] or cid == 8:
            return None
        ev = sorted(e for e in EV.get(cid, []) if e[0] > CLOCK[0])
        return {"data": {"cryptoId": cid, "tokenEvent": [
            {"amount": a, "time": iso(t), "percentage": a / 2e9 * 100,
             "allocations": [{"allocationName": n, "amount": a, "vestingType": v}]} for t, a, v, n in ev]}}
    raise AssertionError(url)


def fake_request(method, path, params=None, signed=True, **kw):
    params = params or {}
    if path == "/fapi/v1/exchangeInfo":
        return {"symbols": [{"symbol": f"{s}USDT", "contractType": "PERPETUAL", "status": "TRADING", "quoteAsset": "USDT",
                             "onboardDate": int((T0 - 400 * D) * 1000), "filters": []}
                            for s in ("AAA", "1000BBB", "DDD", "GGG", "HHH", "FFF", "USDC", "BTC")]}
    if path == "/fapi/v1/premiumIndex":
        s = params["symbol"][:-4]
        return {"markPrice": str(MARK[s]), "lastFundingRate": "0.0001", "nextFundingTime": int((CLOCK[0] + 3600) * 1000)}
    if path == "/fapi/v1/fundingInfo":
        return []
    if path == "/fapi/v1/fundingRate":
        return [{"fundingTime": int(params["startTime"]) + 1000, "fundingRate": "0.0001"}]
    if path in ("/fapi/v1/markPriceKlines", "/fapi/v1/klines"):
        s = params["symbol"][:-4]; st = int(params["startTime"]); n = int(params["limit"])
        p = MARK[s]
        return [[st + i * 60000, p, p * 1.01, p * 0.99, p, 0, st + i * 60000 + 59999] for i in range(n)
                if st + i * 60000 + 59999 < CLOCK[0] * 1000]
    raise AssertionError(path)


scanner.http_json = fake_http_json
trader._request = fake_request
state = {}


def run(label):
    LOG.clear()
    msgs = scanner.unlock_rule(state)
    return msgs


def check(cond, what):
    print(("ОК   " if cond else "СБОЙ ") + what)
    if not cond:
        print("\n".join(LOG)); raise SystemExit(1)


# 1. первый проход — только список монет (14 запросов в реальности, здесь 2 страницы по 5)
m = run("список")
u = state["ul"]
check(CALLS["listing"] == 2 and len(u["tok"]) == 6 and CALLS["event"] == 0,
      f"список: страниц 2, монет с фьючерсом 6 (без CCC и USDC), расписание — со следующего прохода; tok={sorted(u['tok'])}")
check(u["tok"]["2"][1] == "1000BBB", "BBB → фьючерс 1000BBB")
# 2. проходы по очереди: FFF не отдаётся 3 раза
for i in range(6):
    CLOCK[0] += 60; run(f"проход {i}")
    if "queue" not in u:
        break
check("queue" not in u and "tok" not in u, "очередь пройдена, временные данные убраны")
keys = sorted(u["sched"])
check(any(k.startswith("AAA:") for k in keys) and any(k.startswith("1000BBB:") for k in keys) and any(k.startswith("DDD:") for k in keys),
      f"кандидаты AAA, 1000BBB, DDD: {keys}")
a = next(c for k, c in u["sched"].items() if k.startswith("AAA:"))
check(abs(a["T"] - T1) < 1 and abs(a["size"] - 10.5) < 0.01 and a["cliff"],
      f"AAA: разлок по крупнейшему событию (T1, не мелкий день раньше), доля 10% + 0,5% следующих 2 сут = {a['size']}")
check(not any(k.startswith("HHH:") for k in keys), "HHH: cliff 4% и linear 20% — не крупные")
g = [x for x in LOG]
check(any("GGG" in x and "срок входа" in x for x in sum([LOG], [])) or "GGG" not in str(keys), "GGG: срок входа прошёл")
print("   журнал:", *[x for x in LOG if "РАЗЛОК" in x], sep="\n   ")
# 3. до срока входа — сделок нет
CLOCK[0] = T1 - 7 * D - 60; m = run("до входа")
check(not m and not state.get("virtual_UL", {}).get("trades"), "за минуту до срока сделок нет")
# новое обновление расписания на следующий день — тот же кандидат, без повторного входа позже
# 4. срок входа AAA
CLOCK[0] = T1 - 7 * D + 30
m = run("вход AAA")
tr = state["virtual_UL"]["trades"]
check(len(m) == 1 and tr[-1]["sym"] == "AAA" and abs(tr[-1]["hold_h"] - (T1 + D - CLOCK[0]) / 3600) < 0.01,
      f"вход AAA: сообщение, срок сделки до T1 + 1 сут ({tr[-1]['hold_h']} ч)")
check(abs(tr[-1]["sl"] - 1.5) < 1e-9 and tr[-1]["tp"] is None and tr[-1]["lev"] == 1 and tr[-1].get("hedge_sym") == "BTC",
      "стоп +50%, без тейка, плечо ×1, хедж BTC")
print("   сообщение:", m[0].replace("\n", " | "))
for i in range(4):                        # дойти до конца обновления, начатого раньше
    CLOCK[0] += 60; run("доход очереди")
u = state["ul"]; u["list_t"] = 0; u.pop("queue", None); u["err"] = 0
FAIL["listing"] = True                    # список не отдаётся — повтор через 10 мин, сообщение раз в 6 ч
CLOCK[0] += 60; run("сбой списка")
check(any("не отдал список" in x for x in LOG), "сбой списка CMC — строка в журнале")
n0 = CALLS["listing"]; CLOCK[0] += 120; run("повтор раньше 10 мин")
check(CALLS["listing"] == n0, "после сбоя списка — не чаще раза в 10 мин")
CLOCK[0] += 600; LOG.clear(); scanner.unlock_rule(state)
check(CALLS["listing"] == n0 + 1 and not any("не отдал список" in x for x in LOG), "повтор через 10 мин, сообщение — не чаще раза в 6 ч")
FAIL["listing"] = False
# 5. обновление расписания после входа — AAA не входит снова
CLOCK[0] += 700
for i in range(8):
    run(f"обновление {i}"); CLOCK[0] += 60
check(sum(1 for t in state["virtual_UL"]["trades"] if t["sym"] == "AAA") == 1, "после обновления AAA второй раз не входит")
# 6. DDD — цена фьючерса не та
CLOCK[0] = T3 - 7 * D + 10; m = run("DDD")
check(not any(t["sym"] == "DDD" for t in state["virtual_UL"]["trades"]) and any("другой токен" in x for x in LOG),
      "DDD: цена фьючерса 0,10 от CMC — сделки нет")
# 7. устаревшее расписание: CMC не отвечает двое суток — вход ждёт, потом срок проходит
FAIL["listing"] = True; FAIL["events"] = True
CLOCK[0] = T2 - 7 * D - 2 * D                       # последнее обновление было раньше; дальше обновлений нет
for _ in range(3):
    run("без обновлений"); CLOCK[0] += 600
b = next((c for k, c in state["ul"]["sched"].items() if k.startswith("1000BBB:")), None)
CLOCK[0] = T2 - 7 * D + 6 * 3600; m = run("BBB устарело")
stale = (CLOCK[0] - b["chk"]) / 3600 if b else 0
check(b is not None and stale > scanner.UL_STALE_H and not m and any("не обновлялось" in x for x in LOG),
      f"1000BBB: расписание не обновлялось {stale:.0f} ч — вход ждёт обновления")
FAIL["listing"] = False; FAIL["events"] = False
state["ul"]["next"] = 0; state["ul"]["list_t"] = 0
CLOCK[0] += 300
for i in range(4):
    m = run(f"обновление {i}") or m; CLOCK[0] += 60
check(any(t["sym"] == "1000BBB" for t in state["virtual_UL"]["trades"]), "после обновления расписания 1000BBB вошёл (в пределах 24 ч)")
bt = next(t for t in state["virtual_UL"]["trades"] if t["sym"] == "1000BBB")
check(abs(bt["opened"] + bt["hold_h"] * 3600 - (T2 + D)) < 60, "выход 1000BBB — через сутки после разлока, хотя вошли позже")
# 8. выход по времени AAA через сутки после разлока
CLOCK[0] = T1 + D + 120
out = trader.virt_manage(state)
ta = next(t for t in state["virtual_UL"]["trades"] if t["sym"] == "AAA")
check(ta.get("closed") and "выход по времени" in ta.get("reason", ""), f"AAA закрыт по времени: {ta.get('reason')}")
print("   закрытие:", next(x for x in out if "AAA" in x).replace("\n", " | "))
print("\nВсе проверки пройдены")
