"""s139 — тест журнала 🔑 (scanner.insider_unlock_rule) с подменой ответов DefiLlama, coins.llama.fi и Binance: список
и файлы проектов по проходам, сложение событий одних суток, доля к монетам в обращении по расписанию (без noncirculating),
порог 1%, только команда и инвесторы, сверка цены, опоздание, сбои DefiLlama, устаревшее расписание, одна сделка на монету
за 7 сут, повторное обновление без повторного входа, выход по времени через сутки после разлока."""
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

T1 = T0 + 8 * D + 3600                  # AAA: инсайдерам 10% + инвесторам 2% в те же сутки
T2 = T0 + 9.5 * D                       # BBB (фьючерс 1000BBB): инвесторам 3%
T3 = T0 + 8 * D + 7200                  # DDD: команде 8%, но цена фьючерса не та
T4 = T0 + 5 * D                         # GGG: команде 6% — срок входа уже прошёл
T5 = T0 + 8.5 * D                       # EEE: команде 3%, и ещё раз через 5 сут — вторую сделку не открыть
SUP = 1e9                               # монет в обращении по расписанию к моменту разлоков


def proj(name, token, events, treasury=0.0):
    """Файл проекта DefiLlama: раздел «Public» с SUP монет до T0 + 30 сут, раздел казны (noncirculating) — не считается."""
    sec = [{"label": "Public", "data": [{"timestamp": T0 - 400 * D + k * D, "unlocked": SUP, "rawEmission": 0, "burned": 0}
                                        for k in range(431)]}]
    if treasury:
        sec.append({"label": "Treasury", "data": [{"timestamp": T0 - 10 * D, "unlocked": treasury}]})
    ev = [{"description": f"A cliff of {{tokens[0]}} tokens was unlocked from {lab} on {{timestamp}}", "timestamp": str(t),
           "noOfTokens": [n], "category": cat, "unlockType": typ} for t, n, cat, typ, lab in events]
    return {"name": name, "gecko_id": None, "categories": {"noncirculating": ["Treasury"], "insiders": ["Team"]},
            "documentedData": {"data": sec}, "metadata": {"token": token, "events": ev}}


PROJ = {
    "aaa": proj("AAA", "ethereum:0xaaa", [(T1, 1e8, "insiders", "cliff", "Team"), (T1 + 1800, 2e7, "privateSale", "cliff", "Investors"),
                                          (T1 - 2 * D, 5e8, "airdrop", "cliff", "Airdrop"), (T1, 9e8, "insiders", "linear", "Team")],
                treasury=5e9),          # казна не входит в обращение: иначе доля была бы 12% / 6
    "bbb": proj("BBB", "coingecko:bbb", [(T2, 3e7, "privateSale", "cliff", "Seed")]),
    "ccc": proj("CCC", "ethereum:0xccc", [(T0 + 8 * D, 2e8, "insiders", "cliff", "Team")]),        # нет фьючерса
    "ddd": proj("DDD", "ethereum:0xddd", [(T3, 8e7, "insiders", "cliff", "Team")]),
    "usdc": proj("USDC", "ethereum:0xusdc", [(T0 + 8 * D, 2e8, "insiders", "cliff", "Team")]),     # стейблкоин
    "ggg": proj("GGG", "ethereum:0xggg", [(T4, 6e7, "insiders", "cliff", "Team")]),
    "hhh": proj("HHH", "ethereum:0xhhh", [(T0 + 8 * D, 5e6, "insiders", "cliff", "Team"),          # 0,5% — мимо
                                          (T0 + 8 * D, 1e8, "ecosystem", "cliff", "Ecosystem")]),   # не инсайдеры — мимо
    "eee": proj("EEE", "ethereum:0xeee", [(T5, 3e7, "insiders", "cliff", "Team"), (T5 + 5 * D, 3e7, "insiders", "cliff", "Team")]),
    "fff": None,                                                                                   # расписание не отдаётся
    "kkk": dict(proj("KKK", "sui:0xkkk::kkk::KKK", [(T0 + 9 * D, 4e7, "insiders", "cliff", "Team")]), gecko_id="kkk-protocol"),
}
PROJ.update({f"zz{i}": proj(f"ZZ{i}", f"ethereum:0xz{i}", []) for i in range(15)})                # без разлоков — на 3 прохода
PRICE = {"ethereum:0xaaa": ("AAA", 1.0), "coingecko:bbb": ("BBB", 2e-5), "ethereum:0xccc": ("CCC", 1.0),
         "ethereum:0xddd": ("DDD", 1.0), "ethereum:0xusdc": ("USDC", 1.0), "ethereum:0xggg": ("GGG", 1.0),
         "ethereum:0xhhh": ("HHH", 1.0), "ethereum:0xeee": ("EEE", 1.0), "coingecko:kkk-protocol": ("KKK", 1.0)}
FAIL = {"list": False, "proj": False, "binance": False}
CALLS = {"list": 0, "proj": 0, "price": 0}
MARK = {"AAA": 1.0, "1000BBB": 0.02, "DDD": 0.1, "GGG": 1.0, "HHH": 1.0, "EEE": 1.0, "KKK": 1.0, "USDC": 1.0, "BTC": 90000.0}


def fake_gz(url, timeout=30):
    if url == scanner.IU_LIST:
        CALLS["list"] += 1
        return None if FAIL["list"] else sorted(PROJ)
    slug = url.rsplit("/", 1)[1]
    CALLS["proj"] += 1
    if FAIL["proj"] or PROJ.get(slug) is None:
        return None
    return PROJ[slug]


def fake_http_json(url, timeout=30):
    if url.startswith("https://coins.llama.fi/prices/current/"):
        CALLS["price"] += 1
        key = scanner.urllib.parse.unquote(url.rsplit("/", 1)[1])
        if key not in PRICE:
            return {"coins": {}}                                       # адреса нет в coins.llama.fi
        sym, px = PRICE[key]
        return {"coins": {key: {"symbol": sym.lower(), "price": px, "confidence": 0.99}}}
    raise AssertionError(url)


def fake_request(method, path, params=None, signed=True, **kw):
    params = params or {}
    if path == "/fapi/v1/exchangeInfo":
        if FAIL["binance"]:
            return None
        return {"symbols": [{"symbol": f"{s}USDT", "contractType": "PERPETUAL", "status": "TRADING", "quoteAsset": "USDT",
                             "onboardDate": int((T0 - 400 * D) * 1000), "filters": []}
                            for s in ("AAA", "1000BBB", "DDD", "GGG", "HHH", "EEE", "KKK", "USDC", "BTC")]}
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


scanner._http_gz = fake_gz
scanner.http_json = fake_http_json
trader._request = fake_request
state = {}


ALL = []


def run():
    LOG.clear()
    m = scanner.insider_unlock_rule(state)
    ALL.extend(LOG)
    return m


def check(cond, what):
    print(("ОК   " if cond else "СБОЙ ") + what)
    if not cond:
        print("\n".join(LOG)); raise SystemExit(1)


def trades():
    return state.get("virtual_IU", {}).get("trades", [])


# 1. первый проход — только список проектов
run()
u = state["iu"]
check(CALLS["list"] == 1 and CALLS["proj"] == 0 and len(u["queue"]) == len(PROJ), f"список: проектов {len(u['queue'])}, файлы — со следующего прохода")
# 2. проходы по 10 проектов; FFF не отдаётся 3 раза; в первом проходе Binance не отдаёт список контрактов
FAIL["binance"] = True; CLOCK[0] += 60; run(); FAIL["binance"] = False
check(not u["sched"] and any(n >= 1 for n in u["tries"].values()), "Binance не отдал контракты — проекты с разлоками повторятся в этом обновлении")
for i in range(6):
    CLOCK[0] += 60; run()
    if "queue" not in u:
        break
check("queue" not in u and "tries" not in u, "очередь пройдена, временные данные убраны")
keys = sorted(u["sched"])
check(any(k.startswith("AAA:") for k in keys) and any(k.startswith("1000BBB:") for k in keys) and any(k.startswith("DDD:") for k in keys)
      and any(k.startswith("EEE:") for k in keys), f"кандидаты AAA, 1000BBB, DDD, EEE, KKK: {keys}")
a = next(c for k, c in u["sched"].items() if k.startswith("AAA:"))
check(abs(a["T"] - T1) < 1 and abs(a["share"] - 12.0) < 0.01 and a["names"] == ["Investors", "Team"],
      f"AAA: события одних суток сложены (10% + 2%), казна не в обращении, linear и airdrop мимо — доля {a['share']}%, {a['names']}")
check(not any(k.startswith(("CCC:", "USDC:", "HHH:")) for k in keys), "CCC (нет фьючерса), USDC (стейблкоин), HHH (0,5% и экосистема) — мимо")
check(any(k.startswith("KKK:") for k in keys), "KKK: адреса нет в coins.llama.fi — тикер и цена по id CoinGecko")
check(any("fff" in x and "не отдала расписание" in x for x in ALL), "FFF: 3 сбоя — до следующего обновления")
check(sum(1 for k in keys if k.startswith("EEE:")) == 1, "EEE: второй разлок через 13,5 сут — за горизонтом 10 сут")
plus = sorted(k for k in keys if k.startswith("+"))
check(any(k.startswith("+HHH:") for k in plus) and not any(k.startswith("HHH:") for k in keys)
      and all(any(k.startswith(f"+{x}:") for k in plus) for x in ("1000BBB", "DDD", "EEE", "KKK")),
      f"🔑⁺: HHH (экосистема 10%) — только у двойника; 1000BBB, DDD, EEE, KKK — у обоих: {plus}")
iua = lambda: state.get("virtual_IUA", {}).get("trades", [])
check(any(t["sym"] == "AAA" for t in iua()) and not trades(),
      "🔑⁺: AAA — аирдроп 50% за 2 сут до разлока команде, срок входа прошёл меньше 24 ч назад — вход с опозданием")
print("   журнал:", *[x for x in ALL if "РАЗЛОК" in x], sep="\n   ")
# 3. GGG: срок входа прошёл больше 24 ч назад — отмечен в обработанных в том же проходе
check(any("GGG" in x and "срок входа" in x for x in ALL) and any(k.startswith("GGG:") for k in u["done"])
      and not any(k.startswith("GGG:") for k in u["sched"]), "GGG: срок входа прошёл")
# 4. HHH: разлок только сообществу — вход одного 🔑⁺ своим сообщением
CLOCK[0] = T0 + 1 * D + 30; m = run()
check(len(m) == 1 and m[0].startswith("🔑⁺") and "HHH" in m[0] and any(t["sym"] == "HHH" for t in iua())
      and not any(t["sym"] == "HHH" for t in trades()), "HHH: вход только 🔑⁺, отдельным сообщением")
print("   сообщение:", m[0].replace("\n", " | "))
# до срока входа 🔑 — сделок 🔑 нет; срок AAA — вход
CLOCK[0] = T1 - 7 * D - 60; m = run()
check(not m and not trades(), "за минуту до срока сделок нет")
CLOCK[0] = T1 - 7 * D + 30; m = run()
tr = trades()
check(len(m) == 1 and tr[-1]["sym"] == "AAA" and abs(tr[-1]["hold_h"] - (T1 + D - CLOCK[0]) / 3600) < 0.01,
      f"вход AAA: сообщение, срок до T1 + 1 сут ({tr[-1]['hold_h']} ч)")
check(abs(tr[-1]["sl"] - 1.5) < 1e-9 and tr[-1]["tp"] is None and tr[-1]["lev"] == 1 and tr[-1].get("hedge_sym") == "BTC",
      "стоп +50%, без тейка, плечо ×1, хедж BTC")
print("   сообщение:", m[0].replace("\n", " | "))
# 5. сбой списка — повтор через 10 мин, строка раз в 6 ч
u["list_t"] = 0; u.pop("queue", None); u["err"] = 0
FAIL["list"] = True; CLOCK[0] += 60; run()
check(any("не отдала список" in x for x in LOG), "сбой списка DefiLlama — строка в журнале")
n0 = CALLS["list"]; CLOCK[0] += 120; run()
check(CALLS["list"] == n0, "после сбоя — не чаще раза в 10 мин")
CLOCK[0] += 600; run()
check(CALLS["list"] == n0 + 1 and not any("не отдала список" in x for x in LOG), "повтор через 10 мин, строка — не чаще раза в 6 ч")
FAIL["list"] = False
# 6. новое обновление — AAA второй раз не входит
CLOCK[0] += 700
for i in range(8):
    run(); CLOCK[0] += 60
check(sum(1 for t in trades() if t["sym"] == "AAA") == 1, "после обновления AAA второй раз не входит")
# 7. DDD: цена фьючерса не та
CLOCK[0] = T3 - 7 * D + 10; run()
check(not any(t["sym"] == "DDD" for t in trades()) and any("другой токен" in x for x in LOG), "DDD: цена фьючерса 0,10 от DefiLlama — сделки нет")
# 8. EEE: вход по первому разлоку
CLOCK[0] = T5 - 7 * D + 30; m = run()
check(any(t["sym"] == "EEE" for t in trades()), "EEE: вход по первому разлоку")
check(len(m) == 1 and "🔑⁺ тот же шорт" in m[0] and any(t["sym"] == "EEE" for t in iua()),
      "EEE: совместный вход 🔑 и 🔑⁺ — одной строкой к сообщению 🔑")
print("   сообщение:", m[0].replace("\n", " | "))
# 9. устаревшее расписание: DefiLlama не отвечает двое суток — вход ждёт; после обновления — вход в пределах 24 ч
FAIL["list"] = True; FAIL["proj"] = True
b = next((c for k, c in u["sched"].items() if k.startswith("1000BBB:")), None)
check(b is not None, "1000BBB в расписании")
b["chk"] = T2 - 7 * D - 2 * D                         # последнее обновление — двое суток до срока входа
CLOCK[0] = T2 - 7 * D + 3600; m = run()
check(not any(t["sym"] == "1000BBB" for t in trades()) and any("не обновлялось" in x for x in LOG), "1000BBB: расписание устарело — вход ждёт")
FAIL["list"] = False; FAIL["proj"] = False; u["next"] = 0; u["list_t"] = 0; u.pop("queue", None)
for i in range(6):
    run(); CLOCK[0] += 60
check(any(t["sym"] == "1000BBB" for t in trades()), "после обновления 1000BBB вошёл (в пределах 24 ч после срока)")
bt = next(t for t in trades() if t["sym"] == "1000BBB")
check(abs(bt["opened"] + bt["hold_h"] * 3600 - (T2 + D)) < 60, "выход 1000BBB — через сутки после разлока, хотя вошли позже")
# 10. EEE: обновление добавляет второй разлок через 5 сут — сделка открыта и была меньше 7 сут назад → пропуск
u["list_t"] = 0; u.pop("queue", None)
CLOCK[0] = T5 + 5 * D - 7 * D - 3600                  # за час до срока второго входа: второй разлок — в горизонте 10 сут
for i in range(8):
    run(); CLOCK[0] += 60
check(any(k.startswith("EEE:") for k in u["sched"]), "EEE: второй разлок в расписании")
CLOCK[0] = T5 + 5 * D - 7 * D + 30; run()
check(sum(1 for t in trades() if t["sym"] == "EEE") == 1 and any("EEE" in x and "открыта или была" in x for x in LOG),
      "EEE: второй разлок — сделка открыта / была меньше 7 сут назад, пропуск")
check(sum(1 for t in iua() if t["sym"] == "EEE") == 1 and sum(1 for x in LOG if "EEE" in x and "открыта или была" in x) == 2,
      "EEE: и у 🔑⁺ второй вход пропущен — свой учёт 7 сут")
# 11. выход по времени AAA
CLOCK[0] = T1 + D + 120
out = trader.virt_manage(state)
ta = next(t for t in trades() if t["sym"] == "AAA")
check(ta.get("closed") and "выход по времени" in ta.get("reason", ""), f"AAA закрыт по времени: {ta.get('reason')}")
print("   закрытие:", next(x for x in out if "AAA" in x).replace("\n", " | "))
# 12. EEE: совместная сделка 🔑 и 🔑⁺ закрывается в одном проходе — строкой к сообщению 🔑
CLOCK[0] = T5 + D + 120
out = trader.virt_manage(state)
e = [x for x in out if "EEE" in x]
check(len(e) == 1 and e[0].startswith("🔑 ") and "\n🔑⁺ выход по времени" in e[0], "EEE: закрытие 🔑⁺ — строкой к сообщению 🔑")
print("   закрытие:", e[0].replace("\n", " | "))
print("\nВсе проверки пройдены")
