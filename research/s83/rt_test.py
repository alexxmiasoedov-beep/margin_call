"""Тест журнала 👀 (scanner.retail_top_rule) с подменой Upbit, Bithumb и спота Binance. Запуск: python3 research/s83/rt_test.py
из корня репозитория. Состояние — во временной папке, сеть не нужна."""
import os
import sys
import tempfile
import time

os.environ["STATE_FILE"] = os.path.join(tempfile.mkdtemp(), "state.json")
os.environ["POSITION_USDT"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner, trader  # noqa: E402

H0 = 1_790_000_000 // 3600
CLOCK = [H0 * 3600 + 120]
time.time = lambda: CLOCK[0]
trader.mark_price = lambda sym: 1.0
trader.funding_hourly = lambda sym: None
fails = []


def check(cond, what):
    print(("OK   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


UP_FX, BT_FX, TRY_FX = 1400.0, 1350.0, 42.0
MAJ = set().union(*scanner.RT_MAJORS.values()) | scanner.KT_MAJORS
VOL, TRY = {}, {}                                                   # монета → ($ Upbit, $ Bithumb); монета → $ к лире
FAIL = {"upbit": False, "spot": False}
CALLS = {"upbit": 0, "bithumb": 0, "spot": 0}
ONBOARD = {}


def base():
    VOL.clear(); TRY.clear()
    up, bt = scanner.RT_MAJORS["upbit"], scanner.RT_MAJORS["bithumb"]
    for c in MAJ | {"USDC"}:                                        # лидеры — больше всех только в своём списке
        u, b = (900e6 if c in up or c == "USDC" else 0.0), (900e6 if c in bt or c == "USDC" else 0.0)
        if u or b:
            VOL[c] = (u, b)
        if c in scanner.RT_MAJORS["try"] or c == "USDC":
            TRY[c] = 900e6
    for i, v in enumerate((50, 40, 30, 20, 10), 1):
        VOL[f"AA{i}"] = (v * 1e6, 1e6)                              # пятёрка Upbit
        VOL[f"BB{i}"] = (1e6, (110 - 10 * i) * 1e6)                 # пятёрка Bithumb: 100…60 млн $ — она же общая пятёрка 🔝
        TRY[f"TT{i}"] = v * 1e6                                     # пятёрка пар к лире
    VOL["NOFUT"] = (800e6, 800e6); TRY["NOFUT"] = 800e6             # монеты нет на Binance — не в рейтинге


def http_json(url, timeout=30):
    ex = "upbit" if "upbit" in url else "bithumb"
    CALLS[ex] += 1
    if FAIL.get(ex):
        return None
    out = []
    for m in url.split("markets=")[1].split(","):
        c = m[4:]
        fx = UP_FX if ex == "upbit" else BT_FX
        if c == "USDT":
            out.append({"market": m, "trade_price": fx, "acc_trade_price_24h": 1e12})
        elif c in VOL:
            out.append({"market": m, "trade_price": 1.0, "acc_trade_price_24h": VOL[c][0 if ex == "upbit" else 1] * fx})
    return out


def spot_json(path, timeout=15):
    CALLS["spot"] += 1
    if FAIL["spot"]:
        return None
    assert path.startswith("/api/v3/ticker/24hr")
    rows = [{"symbol": "USDTTRY", "lastPrice": str(TRY_FX), "quoteVolume": "1e12"}]
    rows += [{"symbol": f"{c}TRY", "lastPrice": "1", "quoteVolume": str(v * TRY_FX)} for c, v in TRY.items()]
    rows += [{"symbol": "TT1USDT", "lastPrice": "1", "quoteVolume": "1e15"}]  # не пара к лире — не считается
    return rows


CONTRACTS = {f"{c}USDT" for c in MAJ if c not in ("SHIB", "PEPE", "BONK")} | {"1000SHIBUSDT", "1000PEPEUSDT", "1000BONKUSDT"}
CONTRACTS |= {f"{p}{i}USDT" for p in ("AA", "BB", "TT") for i in range(1, 6)}
CONTRACTS |= {"UUUUSDT", "BXUSDT", "TNEWUSDT", "TSPUSDT", "TOLDUSDT", "YNGUSDT", "USDCUSDT"}
scanner.http_json = http_json
scanner.spot_json = spot_json
scanner._kr_list = lambda: {"upbit": set(VOL) | {"USDT"}, "bithumb": set(VOL) | {"USDT"}}
trader._contracts = {s: {} for s in CONTRACTS}
trader.contract = lambda sym: ({"symbol": sym, "onboard": ONBOARD.get(sym, 1_700_000_000)}
                               if f"{sym}USDT" in CONTRACTS or sym in CONTRACTS else None)
state = {}


def hour(h, kt_first=True):
    """Проход через h часов после первого (в первые 10 мин часа): 🔝, потом 👀 — как в scan()."""
    CLOCK[0] = (H0 + h) * 3600 + 120
    m1 = scanner.kr_top_rule(state) if kt_first else []
    return m1, scanner.retail_top_rule(state)


def rt():
    return [t["sym"] for t in state.get("virtual_RT", {}).get("trades", [])]


def kt():
    return [t["sym"] for t in state.get("virtual_KT", {}).get("trades", [])]


# 1. первый проход: три пятёрки без своих лидеров, стейблкоина и монеты без фьючерса; сделок нет (первые 7 суток)
base()
for k in CALLS:
    CALLS[k] = 0
_, m = hour(0)
st = state["rt"]
check(set(st["upbit"]) == {f"AA{i}" for i in range(1, 6)}, f"пятёрка Upbit: {sorted(st['upbit'])}")
check(set(st["bithumb"]) == {f"BB{i}" for i in range(1, 6)}, f"пятёрка Bithumb: {sorted(st['bithumb'])}")
check(set(st["try"]) == {f"TT{i}" for i in range(1, 6)}, f"пятёрка пар к лире: {sorted(st['try'])}")
check(not m and not rt(), "первые 7 суток — только история, сделок нет")
check(CALLS["upbit"] == 1 and CALLS["bithumb"] == 1 and CALLS["spot"] == 1,
      f"🔝 и 👀 в одном проходе: один запрос к Upbit, Bithumb и споту Binance ({CALLS})")

# 2. обороты пар к лире — в $ по USDTTRY; не пары к лире не считаются
tv, why = scanner._rt_try_volumes()
check(abs(tv["TT1"] - 50e6) < 1 and "TT1USDT"[:-3] + "X" not in tv and "USDT" in tv and "TT1US" not in tv,
      "оборот пары к лире переведён в $ по USDTTRY; пары не к лире не берутся")

# 3. 👀 ждёт 🔝 того же часа
_, m = hour(1, kt_first=False)
check(state.get("rt_last_T") != (H0 + 1) * 3600, "🔝 этот час ещё не проверил — 👀 ждёт, час не отмечен")
hour(1)
check(state.get("rt_last_T") == (H0 + 1) * 3600, "после 🔝 тот же час проверен")

for h in range(2, 169):
    hour(h)
check(not rt(), "через 7 суток прежние пятёрки — сделок нет")

# 4. UUU входит в пятёрку Upbit, но не в общую пятёрку → шорт 👀, у 🔝 сделки нет
VOL["UUU"] = (45e6, 0.0)
hour(170)
check("UUU" in rt() and "UUU" not in kt(), f"вход в пятёрку одной биржи вне общей пятёрки → шорт 👀 ({rt()})")
t = state["virtual_RT"]["trades"][0]
check(abs(t["tp"] - 0.9) < 1e-9 and abs(t["sl"] - 1.25) < 1e-9, "тейк 10% и стоп 25%")

# 5. BX входит в пятёрку Bithumb и в общую пятёрку: 🔝 открыл шорт в этом часе → 👀 пропускает
VOL["BX"] = (0.0, 95e6)
hour(171)
check("BX" in kt() and "BX" not in rt(), "вход 🔝 в том же часе — 👀 пропускает монету")

# 6. пары к лире: новая монета → шорт; монета с 🛒 10 ч назад — пропуск; с 🛒 30 ч назад — можно
trader._virt(state, "virtual_SP")["trades"] += [{"sym": "TSP", "opened": (H0 + 172) * 3600 - 10 * 3600, "closed": 1, "reason": "тейк"},
                                                 {"sym": "TOLD", "opened": (H0 + 172) * 3600 - 30 * 3600, "closed": 1, "reason": "тейк"}]
TRY.update(TNEW=60e6, TSP=55e6, TOLD=52e6)
hour(172)
check("TNEW" in rt(), "новая монета в пятёрке пар к лире → шорт 👀")
check("TSP" not in rt(), "у монеты вход 🛒 за прошлые сутки — пропуск")
check("TOLD" in rt(), "вход 🛒 был 30 ч назад — не мешает")

# 7. UUU (вход 👀 2 ч назад) входит ещё и в пятёрку пар к лире → новой сделки нет (одна сделка за 7 суток)
TRY["UUU"] = 70e6
n0 = rt().count("UUU")
hour(173)
check(rt().count("UUU") == n0, "вход в другой список через 3 ч — без новой сделки (кулдаун 7 суток)")

# 8. фьючерс моложе суток — пропуск
VOL["YNG"] = (48e6, 0.0); ONBOARD["YNG"] = (H0 + 174) * 3600 - 5 * 3600
hour(174)
check("YNG" not in rt(), "фьючерс моложе суток — пропуск")

# 9. возврат в пятёрку списка через 3 ч (была за 7 суток) — сделки нет; через 8 суток вне пятёрки — новая
del VOL["UUU"]; del TRY["UUU"]
for h in range(175, 178):
    hour(h)
VOL["UUU"] = (45e6, 0.0)
hour(178)
check(rt().count("UUU") == 1, "возврат в пятёрку через 3 ч — сделки нет")
del VOL["UUU"]
for h in range(179, 179 + 8 * 24):
    hour(h)
for tr in state["virtual_RT"]["trades"]:
    tr["closed"] = tr.get("closed") or time.time(); tr["reason"] = tr.get("reason") or "время"
VOL["UUU"] = (45e6, 0.0)
hour(179 + 8 * 24)
check(rt().count("UUU") == 2, "8 суток вне пятёрки и возврат — новый шорт")

# 10. сбой спота Binance — час не отмечается, повтор в следующем проходе
FAIL["spot"] = True
last = state.get("rt_last_T")
hour(180 + 8 * 24)
check(state.get("rt_last_T") == last, "Binance не отдал обороты пар к лире — час не отмечен, повтор")
FAIL["spot"] = False

# 11. настройки журнала и вызов в scan()
cfg = trader.VIRTUALS["virtual_RT"]
check(cfg["icon"] == "👀" and cfg["params"](None) == (10.0, 25.0) and cfg.get("own") and cfg.get("cooldown_h") == 168
      and cfg.get("pause_h") == 0.0 and cfg.get("hold_h", trader.VIRT["hold_h"]) == 48.0,
      "👀: тейк 10 / стоп 25, 48 ч, кулдаун 7 суток, без паузы после стопа")
src = open(scanner.__file__).read()
check(src.index("for msg in kr_top_rule(state):") < src.index("for msg in retail_top_rule(state):"),
      "scan() вызывает retail_top_rule после kr_top_rule")
check(scanner.RT_MAJORS["upbit"] == {"XRP", "BTC", "ETH", "DOGE", "SOL", "SUI", "ONDO", "ADA", "SHIB", "XLM"}
      and scanner.RT_MAJORS["bithumb"] == {"XRP", "BTC", "ETH", "DOGE", "SOL", "WLD", "VIRTUAL", "SUI", "PEPE", "ONDO"}
      and scanner.RT_MAJORS["try"] == {"XRP", "PEPE", "ETH", "BTC", "DOGE", "PNUT", "NEIRO", "SOL", "BONK", "ENA"},
      "лидеры списков — как в бэктесте s73 и s67")

print("\nВсе проверки пройдены" if not fails else f"\nНЕ ПРОЙДЕНО: {len(fails)}")
sys.exit(1 if fails else 0)
