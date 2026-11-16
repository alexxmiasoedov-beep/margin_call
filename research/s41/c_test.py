"""Тест двойника 📘ᶜ (scanner.chng_confirm) с подменой Binance и постов канала. Запуск: python3 research/s41/c_test.py
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
calls = {"fetch": 0}
fails = []


def check(cond, what):
    print(("OK   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


def post(ts, rows):
    return {"id": int(ts), "ts": ts, "rows": {}, "rows_all": rows}


now = time.time()
state = {}

# 1. CHNG 3.32 два часа назад → двойник открыт
posts = [post(now - 7 * 3600, {}), post(now - 2 * 3600, {"AAA": ("268.4K", "79.1K", "3.4", "3.32")}), post(now - 60, {"AAA": ("268.4K", "85K", "3.2", "3.32")})]
m = scanner.chng_confirm(state, "AAA", 1.0, "pump", posts, now)
check(m is not None and "📘ᶜ" in m and "CHNG 3.32" in m, "CHNG 3.32 за 2 ч → двойник открыт")
check(len(state.get("virtual_1525C", {}).get("trades", [])) == 1, "одна сделка в журнале virtual_1525C")
t = state["virtual_1525C"]["trades"][0]
check(abs(t["tp"] - 0.85) < 1e-9 and abs(t["sl"] - 1.25) < 1e-9, "тейк 15% и стоп 25% как у 📘")
check(t.get("hold_h") == trader.VIRT["hold_h"], "срок сделки как у 📘 (VIRT hold_h)")

# 2. повторный сигнал, пока сделка открыта → не открывается
m = scanner.chng_confirm(state, "AAA", 1.0, "pump", posts, now)
check(m is None and len(state["virtual_1525C"]["trades"]) == 1, "повторный сигнал при открытой сделке — без второй сделки")

# 3. CHNG 0.62 → нет
posts = [post(now - 7 * 3600, {}), post(now - 1800, {"BBB": ("100K", "20K", "5.0", "0.62")})]
check(scanner.chng_confirm(state, "BBB", 1.0, "pump", posts, now) is None, "CHNG 0.62 — двойник не открыт")

# 4. «+1.00» ровно на пороге → открыт; «-0.64», «inf», «abc» — не мешают
posts = [post(now - 7 * 3600, {}), post(now - 3 * 3600, {"CCC": ("1M", "200K", "5.0", "-0.64")}),
         post(now - 2 * 3600, {"CCC": ("1M", "200K", "5.0", "abc")}), post(now - 3600, {"CCC": ("1M", "200K", "inf", "+1.00")})]
check(scanner.chng_confirm(state, "CCC", 1.0, "dump", posts, now) is not None, "«+1.00» на пороге — открыт, «-0.64» и «abc» не мешают")

# 5. CHNG ≥ 1 только 7 ч назад, посты покрывают 6 ч → нет и без догрузки
orig_fetch = scanner.fetch_posts
scanner.fetch_posts = lambda h, **kw: (calls.__setitem__("fetch", calls["fetch"] + 1), [])[1]
posts = [post(now - 7 * 3600, {"DDD": ("1M", "200K", "5.0", "4.0")}), post(now - 600, {"DDD": ("1M", "200K", "5.0", "0.00")})]
check(scanner.chng_confirm(state, "DDD", 1.0, "pump", posts, now) is None and calls["fetch"] == 0,
      "CHNG ≥ 1 только 7 ч назад — не открыт, догрузки нет (посты покрывают 6 ч)")

# 6. посты прохода только за 5,5 ч, подтверждения в них нет → догрузка находит CHNG за 5,8 ч
more = [post(now - 5.8 * 3600, {"EEE": ("1M", "200K", "5.0", "2.10")}), post(now - 600, {"EEE": ("1M", "200K", "5.0", "0.00")})]
scanner.fetch_posts = lambda h, **kw: (calls.__setitem__("fetch", calls["fetch"] + 1), more)[1]
posts = [post(now - 5.4 * 3600, {}), post(now - 600, {"EEE": ("1M", "200K", "5.0", "0.00")})]
m = scanner.chng_confirm(state, "EEE", 1.0, "pump", posts, now)
check(m is not None and calls["fetch"] == 1, "посты прохода короче 6 ч — одна догрузка, CHNG 2.10 за 5,8 ч найден")

# 7. догрузка не удалась → не открыт, без ошибки
scanner.fetch_posts = lambda h, **kw: []
posts = [post(now - 5.4 * 3600, {}), post(now - 600, {"FFF": ("1M", "200K", "5.0", "0.00")})]
check(scanner.chng_confirm(state, "FFF", 1.0, "pump", posts, now) is None, "догрузка не удалась — не открыт, без ошибки")
scanner.fetch_posts = orig_fetch

# 8. место в описании журналов: двойник после 📘, со ссылкой на него, со своими правилами
keys = list(trader.VIRTUALS)
cfg = trader.VIRTUALS["virtual_1525C"]
check(keys.index("virtual_1525C") > keys.index("virtual_1525"), "двойник идёт после 📘 (порядок закрытия)")
check(cfg.get("twin") == "virtual_1525" and cfg.get("own") is True, "twin = virtual_1525, свои правила (own)")
check(cfg["params"](None) == trader.VIRTUALS["virtual_1525"]["params"](None), "тейк и стоп те же, что у 📘")

# 9. virt_on_signal не открывает двойник сам (только через chng_confirm)
st2 = {}
trader.contract = lambda sym: {"symbol": sym}
msg = trader.virt_on_signal(st2, "GGG", 1.0, "pump")
check("virtual_1525C" not in st2 and "virtual_1525" in st2, "сигнал канала без CHNG — 📘 открыт, 📘ᶜ нет")

# 10. в scan() вызов есть сразу после virt_on_signal
src = open(scanner.__file__).read()
i, j = src.index("trader.virt_on_signal(state, sym, c[\"price\"], rule)"), src.index("chng_confirm(state, sym, c[\"price\"], rule, posts, now)")
check(0 < j - i < 400, "scan(): chng_confirm вызывается сразу после virt_on_signal")

print("\nВсе проверки пройдены" if not fails else f"\nНЕ ПРОЙДЕНО: {len(fails)}")
sys.exit(1 if fails else 0)
