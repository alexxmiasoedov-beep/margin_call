"""Тест журнала 🔝 (scanner.kr_top_rule) с подменой Upbit, Bithumb и Binance. Запуск: python3 research/s65/kt_test.py из корня
репозитория. Состояние — во временной папке, сеть не нужна."""
import os
import sys
import tempfile
import time

os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
os.environ["POSITION_USDT"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner, trader  # noqa: E402

CLOCK = [1_790_000_000 // 3600 * 3600 + 120]
time.time = lambda: CLOCK[0]
trader.mark_price = lambda sym: 1.0
trader.funding_hourly = lambda sym: None
fails = []


def check(cond, what):
    print(("OK   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


UP_FX, BT_FX = 1400.0, 1350.0                                    # курсы KRW-USDT бирж
VOL = {}                                                          # монета → ($ Upbit, $ Bithumb) за 24 ч
FAIL = {"upbit": False}
CONTRACTS = {"BTCUSDT", "ETHUSDT", "XRPUSDT", "DOGEUSDT", "SOLUSDT", "SUIUSDT", "ONDOUSDT", "ADAUSDT", "WLDUSDT", "1000SHIBUSDT",
             "AAAUSDT", "BBBUSDT", "CCCUSDT", "DDDUSDT", "EEEUSDT", "FFFUSDT", "GGGUSDT", "1000PEPEUSDT", "NEWUSDT", "USDCUSDT"}
ONBOARD = {}


def set_vol(**kw):
    VOL.clear()
    for c in ("BTC", "ETH", "XRP", "DOGE", "SOL", "SUI", "ONDO", "ADA", "WLD", "SHIB", "USDC"):
        VOL[c] = (900e6, 500e6)                                  # лидеры и стейблкоин — всегда больше всех
    VOL["NOFUT"] = (800e6, 0.0)                                  # монеты нет на Binance — не в рейтинге
    for c, v in kw.items():
        VOL[c] = v


def http_json(url, timeout=30):
    ex = "upbit" if "upbit" in url else "bithumb"
    if FAIL.get(ex):
        return None
    mk = url.split("markets=")[1].split(",")
    out = []
    for m in mk:
        c = m[4:]
        if c == "USDT":
            out.append({"market": m, "trade_price": UP_FX if ex == "upbit" else BT_FX, "acc_trade_price_24h": 1e12})
        elif c in VOL:
            usd = VOL[c][0 if ex == "upbit" else 1]
            out.append({"market": m, "trade_price": 1.0, "acc_trade_price_24h": usd * (UP_FX if ex == "upbit" else BT_FX)})
    return out


scanner.http_json = http_json
scanner._kr_list = lambda: {"upbit": set(VOL) | {"USDT"}, "bithumb": set(VOL) | {"USDT"}}
trader._contracts = {s: {} for s in CONTRACTS}
trader.contract = lambda sym: ({"symbol": sym, "onboard": ONBOARD.get(sym, 1_700_000_000)}
                               if f"{sym}USDT" in CONTRACTS or sym in CONTRACTS else None)
state = {}


def hour(h):
    """Проход через h часов после первого (в первые 10 мин часа)."""
    CLOCK[0] = (1_790_000_000 // 3600 + h) * 3600 + 120
    return scanner.kr_top_rule(state)


def trades():
    return [t["sym"] for t in state.get("virtual_KT", {}).get("trades", [])]


# 1. первый проход: пятёрка без лидеров, стейблкоинов и монет без фьючерса; сделок нет (первые 7 суток)
set_vol(AAA=(50e6, 10e6), BBB=(40e6, 10e6), CCC=(30e6, 10e6), DDD=(20e6, 10e6), EEE=(10e6, 10e6), FFF=(5e6, 1e6),
        PEPE=(1e6, 1e6))
m = hour(0)
hist = state["kt"]["hist"]
check(set(hist) == {"AAA", "BBB", "CCC", "DDD", "EEE"}, f"пятёрка без лидеров, стейблкоина и монеты без фьючерса: {sorted(hist)}")
check(not m and not trades(), "первые 7 суток — только история, сделок нет")

# 2. перевод в доллары по курсу своей биржи: оборот считается в $, сумма двух бирж
vol, why = scanner._kt_volumes()
check(abs(vol["AAA"] - 60e6) < 1 and abs(vol["EEE"] - 20e6) < 1, "оборот — сумма Upbit + Bithumb в $ по KRW-USDT каждой биржи")

# 3. через 7 суток: пятёрка та же — сделок нет (все были в пятёрке за 7 суток)
for h in range(1, 168):
    hour(h)
m = hour(169)
check(not trades(), "через 7 суток прежняя пятёрка — сделок нет")

# 4. новая монета (1000PEPE) входит в пятёрку → шорт 🔝 по фьючерсу 1000PEPE
set_vol(AAA=(50e6, 10e6), BBB=(40e6, 10e6), CCC=(30e6, 10e6), DDD=(20e6, 10e6), PEPE=(15e6, 10e6), EEE=(10e6, 10e6))
m = hour(170)
check(trades() == ["1000PEPE"] and any("🔝" in x for x in m), f"новая монета в пятёрке → шорт 🔝 по 1000PEPE ({trades()})")
t = state["virtual_KT"]["trades"][0]
check(abs(t["tp"] - 0.9) < 1e-9 and abs(t["sl"] - 1.25) < 1e-9, "тейк 10% и стоп 25%")

# 5. EEE выпала из пятёрки и вернулась через 3 ч (была за 7 суток) — сделки нет
set_vol(AAA=(50e6, 10e6), BBB=(40e6, 10e6), CCC=(30e6, 10e6), DDD=(20e6, 10e6), EEE=(18e6, 10e6), PEPE=(10e6, 10e6))
hour(173)
check(trades() == ["1000PEPE"], "возврат в пятёрку через 3 ч — сделки нет")

# 6. FFF не была в пятёрке никогда, но фьючерс моложе суток — пропуск; GGG — новая, фьючерс старый → шорт
ONBOARD["FFF"] = CLOCK[0] + 3600 - 5 * 3600
set_vol(AAA=(50e6, 10e6), BBB=(40e6, 10e6), CCC=(30e6, 10e6), FFF=(25e6, 10e6), GGG=(22e6, 10e6))
hour(174)
check("FFF" not in trades() and "GGG" in trades(), "фьючерс моложе суток — пропуск; новая монета со старым фьючерсом — шорт")

# 7. DDD и EEE не были в пятёрке 8 суток → снова «впервые за 7 суток» → шорт
set_vol(AAA=(50e6, 10e6), BBB=(40e6, 10e6), CCC=(30e6, 10e6), FFF=(25e6, 10e6), GGG=(22e6, 10e6))
for h in range(175, 175 + 8 * 24):
    hour(h)
set_vol(AAA=(50e6, 10e6), BBB=(40e6, 10e6), CCC=(30e6, 10e6), DDD=(28e6, 10e6), EEE=(27e6, 10e6))
hour(175 + 8 * 24)
check("DDD" in trades() and "EEE" in trades(), "8 суток вне пятёрки и возврат — новый шорт")

# 8. кулдаун: GGG вернулась через 8 суток после выхода, но с её прошлого входа прошло < 7 суток? — проверка на свежей монете
sp = [x for x in state["virtual_KT"]["trades"] if x["sym"] == "DDD"][0]
sp["closed"] = time.time(); sp["reason"] = "тейк"
state["kt"]["hist"].pop("DDD")                                   # будто DDD снова «впервые»
set_vol(AAA=(50e6, 10e6), BBB=(40e6, 10e6), CCC=(30e6, 10e6), DDD=(28e6, 10e6), EEE=(27e6, 10e6))
n0 = trades().count("DDD")
hour(176 + 8 * 24)
check(trades().count("DDD") == n0, "повторный сигнал меньше чем через 7 суток после входа — без новой сделки (кулдаун)")

# 9. сбой Upbit — свеча не отмечается, список рынков перечитывается
FAIL["upbit"] = True
last = state.get("kt_last_T")
m = hour(178 + 8 * 24)
check(m == [] and state.get("kt_last_T") == last and scanner._kr_markets["ts"] == 0,
      "Upbit не ответил — проход повторится, список рынков будет перечитан")
FAIL["upbit"] = False

# 10. настройки журнала и вызов в scan()
cfg = trader.VIRTUALS["virtual_KT"]
check(cfg["icon"] == "🔝" and cfg["params"](None) == (10.0, 25.0) and cfg.get("own") and cfg.get("cooldown_h") == 168
      and cfg.get("pause_h") == 0.0 and cfg.get("hold_h", trader.VIRT["hold_h"]) == 48.0,
      "🔝: тейк 10 / стоп 25, 48 ч, кулдаун 7 суток, без паузы после стопа")
src = open(scanner.__file__).read()
check("for msg in kr_top_rule(state):" in src, "scan() вызывает kr_top_rule")
check(scanner.KT_MAJORS == {"XRP", "BTC", "ETH", "DOGE", "SOL", "SUI", "ONDO", "ADA", "WLD", "SHIB"}, "10 лидеров — как в бэктесте")

print("\nВсе проверки пройдены" if not fails else f"\nНЕ ПРОЙДЕНО: {len(fails)}")
sys.exit(1 if fails else 0)
