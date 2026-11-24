"""Тест двойника 🛒⁸ (virtual_SP8: те же входы, что у 🛒, выход через 8 ч, без тейка, стоп 10%) с подменой Binance.
Запуск из корня репозитория: python3 research/s270/sp8_test.py. Состояние — во временной папке, сеть не нужна."""
import os
import sys
import tempfile
import time

os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
os.environ["POSITION_USDT"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner, trader  # noqa: E402

trader.mark_price = lambda sym: 1.0
trader.funding_hourly = lambda sym: None
trader.funding_paid = lambda sym, a, b: 0.0
fails = []


def check(cond, what):
    print(("OK   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


def kl(t, qv, c=1.0, h=None):
    return [t * 1000, str(c), str(h if h is not None else c), str(c), str(c), "0", t * 1000 + 899999, str(qv), 1, "0", "0", "0"]


H0 = 1_790_000_000 // 3600 * 3600
T = H0 + 900
base = [kl(H0 - 900 * (480 - i), 100e3, 1.0, 1.0) for i in range(472)]
pump = [kl(H0 - 900 * (8 - i), 100e3, 1.0 + 0.02 * i, 1.0 + 0.02 * i) for i in range(8)] + [kl(H0, 5e6, 1.2, 1.2)]


def spot_all(path, timeout=15):
    if path.startswith("/api/v3/ticker/price"):
        return [{"symbol": "AAAUSDT", "price": "1.2"}]
    end = int(path.split("endTime=")[1].split("&")[0]) // 1000 + 1
    lim = int(path.split("limit=")[1].split("&")[0])
    return [kl(end - 900 * (lim - i), 50e3 if lim == 4 else 300e3) for i in range(lim)]


scanner.candle_due = lambda st, key, name, step=900: T
scanner.candle_done = lambda st, key, TT: None
scanner.ticker24 = lambda: [{"symbol": "AAAUSDT", "highPrice": "1.3", "lowPrice": "1.0"}]
trader.contract = lambda sym: {"symbol": sym}
trader._contracts = {"AAAUSDT": {}}
scanner._kr_list = lambda: {"upbit": set(), "bithumb": set()}
scanner._closed_15m = lambda sym, TT, n=99: (base + pump)[-n:] if sym == "AAA" else None
scanner.spot_json = spot_all

# 1. настройки журнала
cfg8 = trader.VIRTUALS["virtual_SP8"]
check(cfg8["icon"] == "🛒⁸" and cfg8["params"](None) == (None, 10.0) and cfg8.get("own"), "🛒⁸: свои сигналы, без тейка, стоп 10%")
check(cfg8.get("hold_h") == 8.0 and cfg8.get("cooldown_h") == 48 and cfg8.get("pause_h") == 0.0,
      "срок 8 ч, одна сделка на монету за 48 ч (как у 🛒 и в бэктесте), без паузы после стопа")
check(cfg8.get("twin") == "virtual_SP", "близнец 🛒")
keys = list(trader.VIRTUALS)
check(keys.index("virtual_SP8") == keys.index("virtual_SP") + 1, "🛒⁸ идёт сразу после 🛒 — закрытия склеиваются по порядку")

# 2. проход korea_rule: памп со спотом 33% → шорт 🛒 и 🛒⁸ одной записью
state = {}
msgs = scanner.korea_rule(state)
sp = state.get("virtual_SP", {}).get("trades", [])
sp8 = state.get("virtual_SP8", {}).get("trades", [])
check(len(sp) == 1 and len(sp8) == 1 and sp8[0]["sym"] == "AAA", "korea_rule: памп со спотом 33% → шорт и в 🛒, и в 🛒⁸")
check(sp8[0]["tp"] is None and abs(sp8[0]["sl"] - 1.1) < 1e-9 and sp8[0]["hold_h"] == 8.0 if sp8 else False,
      "🛒⁸: без тейка, стоп +10% от цены входа, срок сделки 8 ч")
check(abs(sp[0]["sl"] - 1.25) < 1e-9 and sp[0]["hold_h"] == 48.0 if sp else False, "🛒 не изменился: стоп +25%, 48 ч")
check(sum("🛒⁸ тот же шорт" in m for m in msgs) == 1 and not any(m.startswith("🛒⁸") for m in msgs),
      "совместный вход — одна строка к сообщению 🛒, отдельного сообщения нет")

# 3. повторный памп той же монеты, пока сделки открыты, → без новых входов
before = (len(sp), len(sp8))
scanner.korea_rule(state)
check((len(state["virtual_SP"]["trades"]), len(state["virtual_SP8"]["trades"])) == before, "второй проход: новых сделок нет")

# 4. через 8 ч: 🛒⁸ закрыт по времени, 🛒 держит
trader._virt_scan = lambda t: None
for t in sp + sp8:
    t["opened"] -= 8 * 3600 + 60
    t["v_chk"] = 0
msgs = trader.virt_manage(state)
check(sp8[0].get("closed") and sp8[0].get("reason") == "выход по времени (8 ч)", f"🛒⁸ закрыт по времени: {sp8[0].get('reason')}")
check(not sp[0].get("closed"), "🛒 через 8 ч ещё открыт")
check(any(m.startswith("🛒⁸") for m in msgs), "закрытие 🛒⁸ — своим сообщением (🛒 не закрывался)")

# 5. после выхода 🛒⁸ в 48 ч от входа — новой сделки 🛒⁸ нет
check(trader.virt_open(state, "virtual_SP8", "AAA", "SP", "повтор", price=1.0) is None, "в 48 ч от входа 🛒⁸ не входит снова")
sp8[0]["opened"] -= 41 * 3600
check(trader.virt_open(state, "virtual_SP8", "AAA", "SP", "через 49 ч", price=1.0) is not None, "через 49 ч после входа — новая сделка")

# 6. стоп 10%: стоп у обоих в одном проходе → строка 🛒⁸ к сообщению 🛒
state2 = {}
trader.virt_open(state2, "virtual_SP", "BBB", "SP", "тест", price=1.0)
trader.virt_open(state2, "virtual_SP8", "BBB", "SP", "тест", price=1.0)
trader._virt_scan = lambda t: "стоп"
for t in state2["virtual_SP"]["trades"] + state2["virtual_SP8"]["trades"]:
    t["v_chk"] = 0
msgs = trader.virt_manage(state2)
t8 = state2["virtual_SP8"]["trades"][0]
check(t8.get("reason") == "стоп" and abs(t8["exit"] - 1.1) < 1e-9, "🛒⁸: стоп по цене +10%")
check(len(msgs) == 1 and "🛒⁸ стоп" in msgs[0], "оба закрылись в одном проходе — строка 🛒⁸ в сообщении 🛒")

# 7. стоп только у 🛒⁸ — отдельное сообщение, 🛒 открыт
state3 = {}
trader.virt_open(state3, "virtual_SP", "CCC", "SP", "тест", price=1.0)
trader.virt_open(state3, "virtual_SP8", "CCC", "SP", "тест", price=1.0)
trader._virt_scan = lambda t: "стоп" if t.get("sl_pct") == 10.0 else None
for t in state3["virtual_SP"]["trades"] + state3["virtual_SP8"]["trades"]:
    t["v_chk"] = 0
msgs = trader.virt_manage(state3)
check(state3["virtual_SP8"]["trades"][0].get("reason") == "стоп" and not state3["virtual_SP"]["trades"][0].get("closed")
      and len(msgs) == 1 and msgs[0].startswith("🛒⁸"), "стоп только у 🛒⁸ — его сообщение, 🛒 держит")

# 8. выгрузка знает 🛒⁸
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tools", "export_signals.py")).read()
check('("virtual_SP8", "🛒⁸")' in src, "tools/export_signals.py выгружает 🛒⁸")

print("\nВсе проверки пройдены" if not fails else f"\nНЕ ПРОЙДЕНО: {len(fails)}")
sys.exit(1 if fails else 0)
