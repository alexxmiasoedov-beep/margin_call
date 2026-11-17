"""Тест журнала ⏰ «9 утра» (scanner.open9_rule) с подменой Binance, Upbit и Bithumb. Запуск: python3 research/s88/o9_test.py
из корня репозитория. Состояние — во временной папке, сеть не нужна."""
import os
import sys
import tempfile
import time
from datetime import datetime, timezone

os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
os.environ["POSITION_USDT"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner, trader  # noqa: E402

DAY0 = 1_790_000_000 // 86400 * 86400                             # полночь UTC
CLOCK = [DAY0 + 300]
time.time = lambda: CLOCK[0]
trader.mark_price = lambda sym: 1.0
trader.funding_hourly = lambda sym: None
fails = []


def check(cond, what):
    print(("OK   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


UP_FX, BT_FX = 1400.0, 1350.0
# фьючерс → (рост за час 00–01 UTC, оборот фьючерса за час $, Upbit $, Bithumb $, размах за сутки)
MK = {}
UPBIT, BITHUMB = set(), set()
ONBOARD = {}
FAIL = {"kr": set(), "kl": set()}
CALLS = {"kl": []}


def setup(**kw):
    MK.clear(); MK.update(kw)


def kline_rows(sym, T):
    rise, fut = MK[sym][0], MK[sym][1]
    rows = []
    for i in range(6, -1, -1):                                    # 6 закрытых свечей до T и текущая (открытая, i = 0)
        ot = T - i * 900                                          # открытие свечи
        close_t = ot + 900
        c = 1.0 if close_t <= T - 3600 else (1.0 + rise if close_t >= T else 1.0 + rise * (close_t - (T - 3600)) / 3600)
        qv = fut / 4 if T - 3600 < close_t <= T else 1e5
        rows.append([ot * 1000, c, c, c, c, 1.0, close_t * 1000 - 1, qv])
    return rows


def http_json(url, timeout=30):
    T = int(time.time() // 3600 * 3600)
    if "fapi.binance.com/fapi/v1/klines" in url:
        sym = url.split("symbol=")[1].split("USDT")[0]
        CALLS["kl"].append(sym)
        if sym in FAIL["kl"] or sym not in MK:
            return None
        return kline_rows(sym, T)
    ex = "upbit" if "upbit" in url else "bithumb"
    m = url.split("market=")[1].split("&")[0]
    coin = m[4:]
    if coin == "USDT":
        return [{"trade_price": UP_FX if ex == "upbit" else BT_FX}]
    if (ex, coin) in FAIL["kr"]:
        return None
    sym = next(s for s in MK if s.endswith(coin))
    usd = MK[sym][2 if ex == "upbit" else 3]
    fx = UP_FX if ex == "upbit" else BT_FX
    return [{"candle_date_time_utc": datetime.fromtimestamp(T - 3600 + q * 900, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
             "candle_acc_trade_price": usd / 4 * fx} for q in range(4)]


def ticker24():
    return [{"symbol": f"{s}USDT", "highPrice": str(1.0 + MK[s][4]), "lowPrice": "1.0"} for s in MK]


scanner.http_json = http_json
scanner.ticker24 = ticker24
scanner._kr_list = lambda: {"upbit": UPBIT, "bithumb": BITHUMB}
trader.contract = lambda sym: ({"symbol": sym, "onboard": ONBOARD.get(sym.replace("USDT", ""), 1_700_000_000)}
                               if sym.replace("USDT", "") in MK or sym == "BTC" else None)
state = {}


def at(day, hh, mm):
    CLOCK[0] = DAY0 + day * 86400 + hh * 3600 + mm * 60
    trader._contracts = {f"{s}USDT": {} for s in MK}
    return scanner.open9_rule(state)


def opened():
    return sorted(t["sym"] for t in state.get("virtual_O9", {}).get("trades", []))


UPBIT |= {"AAA", "CCC", "DDD", "PEPE", "GGG", "HHH"}
BITHUMB |= {"AAA", "BBB", "CCC", "DDD", "GGG", "HHH"}
setup(AAA=(0.06, 7e6, 2e6, 1e6, 0.10),        # +6%, доля 30% → шорт
      BBB=(0.04, 1e6, 0, 5e6, 0.10),          # рост 4% — нет
      CCC=(0.08, 9e6, 0.5e6, 0.5e6, 0.10),    # +8%, доля 10% — нет
      DDD=(0.07, 1e6, 1e6, 1e6, 0.10),        # фьючерс моложе суток — пропуск
      EEE=(0.09, 1e6, 5e6, 5e6, 0.10),        # монеты нет на корейских биржах — не кандидат
      FFF=(0.06, 1e6, 5e6, 5e6, 0.03),        # размах за сутки < 5% — не кандидат
      **{"1000PEPE": (0.055, 3e6, 1e6, 0, 0.10)})   # 1000PEPE → PEPE на Upbit, доля 25% → шорт
ONBOARD["DDD"] = DAY0 + 3600 - 10 * 3600

# 1. 00:05 UTC — не час открытия: ничего не делает
m = at(0, 0, 5)
check(m == [] and opened() == [] and not CALLS["kl"], "00:05 — не час открытия: сделок и запросов свечей нет")

# 2. 01:05 UTC — час открытия
m = at(0, 1, 5)
check(opened() == ["1000PEPE", "AAA"], f"01:05 — шорты AAA и 1000PEPE (есть: {opened()})")
check(set(CALLS["kl"]) == {"AAA", "BBB", "CCC", "DDD", "1000PEPE"},
      f"свечи запрошены только у кандидатов с рынком к воне и размахом ≥ 5% ({sorted(set(CALLS['kl']))})")
check(len(m) == 2 and all("⏰" in x for x in m), "два сообщения ⏰ в чат")
t = next(x for x in state["virtual_O9"]["trades"] if x["sym"] == "AAA")
check(t["lev"] == 1 and t["tp_pct"] == 10 and t["sl_pct"] == 25 and t["hold_h"] == 48, "плечо ×1, тейк 10 / стоп 25, 48 ч")
check(state.get("o9_last_T") == DAY0 + 3600, "час отмечен проверенным")

# 3. повторный проход в тот же час — без дублей
CALLS["kl"].clear()
m = at(0, 1, 7)
check(m == [] and not CALLS["kl"] and opened() == ["1000PEPE", "AAA"], "01:07 — повторного прохода нет")

# 4. следующий день: сбой Upbit у GGG — повтор; потом данные есть — шорт
setup(GGG=(0.07, 2e6, 1e6, 1e6, 0.10), AAA=(0.06, 7e6, 2e6, 1e6, 0.10))
FAIL["kr"].add(("upbit", "GGG"))
m = at(1, 1, 2)
check(opened() == ["1000PEPE", "AAA"] and state.get("o9_last_T") == DAY0 + 3600,
      "сбой Upbit у GGG — сделки нет, час не отмечен (повтор)")
FAIL["kr"].clear()
m = at(1, 1, 4)
check(opened() == ["1000PEPE", "AAA", "GGG"], f"данные пришли — шорт GGG (есть: {opened()})")
check(sum(1 for x in state["virtual_O9"]["trades"] if x["sym"] == "AAA") == 1,
      "AAA снова вырос, но его сделка ещё открыта — второй нет")
check(state.get("o9_last_T") == DAY0 + 86400 + 3600, "после повтора час отмечен")

# 5. сбой свечей Binance дольше 8 мин — час отмечается без сделки
setup(HHH=(0.09, 1e6, 1e6, 1e6, 0.10))
FAIL["kl"].add("HHH")
m = at(2, 1, 3)
check(state.get("o9_last_T") == DAY0 + 86400 + 3600, "02-й день 01:03: свечей HHH нет — повтор")
m = at(2, 1, 9)
check(state.get("o9_last_T") == DAY0 + 2 * 86400 + 3600 and "HHH" not in opened(),
      "01:09 — окно повтора прошло: час отмечен, HHH без сделки")

# 6. 01:12 — проход опоздал больше чем на 10 мин: свеча пропущена, сделок нет
FAIL["kl"].clear(); setup(HHH=(0.09, 1e6, 1e6, 1e6, 0.10))
m = at(3, 1, 12)
check(m == [] and "HHH" not in opened(), "проход позже 10 мин — свеча пропущена, сделок нет")

print("\nИтог:", "все проверки прошли" if not fails else f"не прошло {len(fails)}: " + "; ".join(fails))
sys.exit(1 if fails else 0)
