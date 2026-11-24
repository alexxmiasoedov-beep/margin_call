"""Тест журнала 🛒 (scanner.spot_pump_check и вход из korea_rule) с подменой Binance. Запуск: python3 research/s49/sp_test.py
из корня репозитория. Состояние — во временной папке, сеть не нужна."""
import os
import sys
import tempfile
import time

os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
os.environ["POSITION_USDT"] = "1"                         # маржа сделки как на сервере (журнал стартует с 20 USDT)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner, trader  # noqa: E402

trader.mark_price = lambda sym: 1.0
trader.funding_hourly = lambda sym: None
fails = []


def check(cond, what):
    print(("OK   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


def kl(t, qv, c=1.0, h=None):
    """Свеча Binance: [время открытия мс, open, high, low, close, vol, время закрытия, оборот $, сделки, ...]."""
    return [t * 1000, str(c), str(h if h is not None else c), str(c), str(c), "0", t * 1000 + 899999, str(qv), 1, "0", "0", "0"]


H0 = 1_790_000_000 // 3600 * 3600                           # начало часа «пампа»
calls = []


def spot_mock(vol_each, fail=False):
    def f(path, timeout=15):
        calls.append(path)
        if fail:
            return None
        end = int(path.split("endTime=")[1].split("&")[0]) // 1000 + 1
        return [kl(end - 3600 + 900 * i, vol_each) for i in range(4)]
    return f


# k — свечи фьючерса: час до H0 по 100 тыс. $ на свечу, свеча пампа (открытие H0) — 5 млн $
k = [kl(H0 - 7200 + 900 * i, 100e3) for i in range(8)] + [kl(H0, 5e6)]
T = H0 + 900                                                  # закрытие свечи пампа — 15 мин после начала часа

# 1. доля 33% ≥ 26% → подходит; спот запрошен по концу полного часа H0
scanner.spot_json = spot_mock(50e3)
ok, why = scanner.spot_pump_check("AAA", "AAA", T, k, {"AAAUSDT": "1"})
check(ok and "33.3%" in why, f"памп в :15, спот 200 тыс. против фьючерса 400 тыс. — 33% → подходит ({why})")
check(f"endTime={H0 * 1000 - 1}" in calls[-1], "спот запрошен за последний полный час (endTime = начало часа пампа − 1 мс)")
check("5.00" not in why and "0.40 млн" in why, "свеча пампа (следующий час) в оборот фьючерса не вошла")

# 2. доля 20% → нет
scanner.spot_json = spot_mock(25e3)
ok, why = scanner.spot_pump_check("AAA", "AAA", T, k, {"AAAUSDT": "1"})
check(not ok and "20.0%" in why, f"спот 100 тыс. против 400 тыс. — 20% → не подходит ({why})")

# 3. памп ровно в начале часа: полный час — тот, что заканчивается закрытием свечи пампа (свеча пампа входит)
k2 = [kl(H0 - 7200 + 900 * i, 100e3) for i in range(7)] + [kl(H0 - 900, 2e6)]
scanner.spot_json = spot_mock(200e3)
ok, why = scanner.spot_pump_check("AAA", "AAA", H0, k2, {"AAAUSDT": "1"})
check(f"endTime={H0 * 1000 - 1}" in calls[-1] and "2.30 млн" in why,
      f"памп в :00 — час заканчивается закрытием пампа, свеча пампа в обороте фьючерса ({why})")
check(not ok, "там же спот 0,8 млн против фьючерса 2,3 млн — 26% не набрано")

# 4. нет спота, сбой спота, монета с множителем
ok, why = scanner.spot_pump_check("BBB", "BBB", T, k, {"AAAUSDT": "1"})
check(not ok and why == "нет спота Binance", "монеты нет на споте Binance → не подходит")
scanner.spot_json = spot_mock(50e3, fail=True)
ok, why = scanner.spot_pump_check("AAA", "AAA", T, k, {"AAAUSDT": "1"})
check(not ok and "не отдал" in why, "спот не ответил → не подходит, пояснение в журнале")
scanner.spot_json = spot_mock(50e3)
ok, why = scanner.spot_pump_check("1000PEPE", "PEPE", T, k, {"PEPEUSDT": "1"})
check(ok and "symbol=PEPEUSDT" in calls[-1], "1000PEPE → спот PEPEUSDT")

# 5. настройки журнала
cfg = trader.VIRTUALS["virtual_SP"]
check(cfg["icon"] == "🛒" and cfg["params"](None) == (10.0, 25.0) and cfg.get("own"), "🛒: свои сигналы, тейк 10 / стоп 25")
check(cfg.get("cooldown_h") == 48 and cfg.get("pause_h") == 0.0 and cfg.get("hold_h", trader.VIRT["hold_h"]) == 48.0,
      "одна сделка на монету за 48 ч, срок 48 ч, без паузы после стопа — как в бэктесте")

# 6. полный проход korea_rule: памп AAA, Кореи нет, спот 33% → шорт 🛒, лонга 🟩 нет (спот ≥ 12%)
state = {}
scanner.candle_due = lambda st, key, name, step=900: T
scanner.candle_done = lambda st, key, TT: None
scanner.ticker24 = lambda: [{"symbol": "AAAUSDT", "highPrice": "1.3", "lowPrice": "1.0"}]
trader.contract = lambda sym: {"symbol": sym}
trader._contracts = {"AAAUSDT": {}}
scanner._kr_list = lambda: {"upbit": set(), "bithumb": set()}
base = [kl(H0 - 900 * (480 - i), 100e3, 1.0, 1.0) for i in range(472)]          # 5 суток тишины
pump = [kl(H0 - 900 * (8 - i), 100e3, 1.0 + 0.02 * i, 1.0 + 0.02 * i) for i in range(8)] + [kl(H0, 5e6, 1.2, 1.2)]
scanner._closed_15m = lambda sym, TT, n=99: (base + pump)[-n:] if sym == "AAA" else None


def spot_all(path, timeout=15):
    if path.startswith("/api/v3/ticker/price"):
        return [{"symbol": "AAAUSDT", "price": "1.2"}]
    end = int(path.split("endTime=")[1].split("&")[0]) // 1000 + 1
    lim = int(path.split("limit=")[1].split("&")[0])
    return [kl(end - 900 * (lim - i), 50e3 if lim == 4 else 300e3) for i in range(lim)]


scanner.spot_json = spot_all
check(scanner._pump_at(base + pump) is not None, "в подменённых свечах есть памп по правилу бота")
msgs = scanner.korea_rule(state)
sp = state.get("virtual_SP", {}).get("trades", [])
check(len(sp) == 1 and sp[0]["sym"] == "AAA" and any("🛒" in m for m in msgs), "korea_rule: памп со спотом 33% → шорт 🛒")
check(abs(sp[0]["tp"] - 0.9) < 1e-9 and abs(sp[0]["sl"] - 1.25) < 1e-9 if sp else False, "тейк −10% и стоп +25% от цены входа")

# 7. повторный памп той же монеты в течение 48 ч → без второй сделки
check(trader.virt_open(state, "virtual_SP", "AAA", "SP", "повтор", price=1.0) is None, "вторая сделка по монете, пока первая открыта, — нет")
sp[0]["closed"] = time.time(); sp[0]["reason"] = "тейк"
check(trader.virt_open(state, "virtual_SP", "AAA", "SP", "повтор", price=1.0) is None, "после закрытия, но в 48 ч от входа — нет")
sp[0]["opened"] -= 49 * 3600
check(trader.virt_open(state, "virtual_SP", "AAA", "SP", "через 49 ч", price=1.0) is not None, "через 49 ч после входа — новая сделка")

# 8. порядок в korea_rule: 🛒 проверяется до 🟩 (лонг) в том же пампе
src = open(scanner.__file__).read()
i, j = src.index("ok_sp, why_sp = spot_pump_check(s, coin, T, k, spot)"), src.index("ok, why = noretail_check(s, coin, T, fut, kr_share, spot)")
check(0 < j - i < 2000, "korea_rule: проверка 🛒 (и вход 🛒⁸) стоит перед проверкой 🟩")   # 24.11: + вход двойника 🛒⁸

print("\nВсе проверки пройдены" if not fails else f"\nНЕ ПРОЙДЕНО: {len(fails)}")
sys.exit(1 if fails else 0)
