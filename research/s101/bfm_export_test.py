"""Тест двойника 🏦ᵐ (scanner._bf_open) и команды /export (scanner.export_start, export_check) с подменой Binance и Telegram.
Запуск: python3 research/s101/bfm_export_test.py из корня репозитория. Состояние и файлы — во временной папке."""
import os
import sys
import tempfile
import time

TMP = tempfile.mkdtemp()
os.environ["STATE_FILE"] = os.path.join(TMP, "state.json")
os.environ["POSITION_USDT"] = "1"
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "bot"))
import scanner, trader  # noqa: E402

fails = []
LOGS = []
scanner.log = lambda *a, **k: LOGS.append(" ".join(str(x) for x in a))
trader.log = scanner.log


def check(cond, what):
    print(("OK   " if cond else "FAIL ") + what)
    if not cond:
        fails.append(what)


PX = {"AAA": 0.05, "BBB": 1.0, "CCC": 2.0, "BTC": 90000.0}
trader.mark_price = lambda sym: PX.get(sym)
trader.funding_hourly = lambda sym: None
state = {"ul": {"circ": {"AAA": 1e9, "BBB": 1e6}}}

# 1. крупная монета: 50 млн $ ≥ 30 млн $ — входят 🏦, 🏦³ и 🏦ᵐ, одной строкой
m = scanner._bf_open(state, "AAA", "заметка", 0.05)
keys = lambda k: [t["sym"] for t in state.get(k, {}).get("trades", [])]
check(keys("virtual_BF") == ["AAA"] and keys("virtual_BF3") == ["AAA"] and keys("virtual_BFM") == ["AAA"], "AAA: все три журнала вошли")
check(len(m) == 1 and "🏦³ тот же шорт" in m[0] and "🏦ᵐ тот же шорт (капитализация свободного оборота 50 млн $)" in m[0],
      "AAA: одно сообщение с двумя двойниками")
t = state["virtual_BFM"]["trades"][0]
check(t["sl_pct"] == 100 and t["tp_pct"] is None and t["hold_h"] == 168 and t["lev"] == 1 and t.get("hedge_sym") == "BTC",
      "🏦ᵐ: стоп +100%, без тейка, 7 суток, плечо ×1, хедж BTC")

# 2. мелкая монета: 1 млн $ < 30 млн $ — 🏦ᵐ без входа
m = scanner._bf_open(state, "BBB", "заметка", 1.0)
check("BBB" in keys("virtual_BF") and "BBB" not in keys("virtual_BFM"), "BBB: 🏦 и 🏦³ вошли, 🏦ᵐ нет")
check(len(m) == 1 and "🏦ᵐ без входа: капитализация свободного оборота 1 млн $ — меньше 30 млн $" in m[0], "BBB: причина в сообщении")

# 3. нет данных CoinMarketCap — вход
m = scanner._bf_open(state, "CCC", "заметка", 2.0)
check("CCC" in keys("virtual_BFM") and "нет данных CoinMarketCap" in m[0], "CCC без данных: 🏦ᵐ вошёл")

# 4. повтор — без дублей
m = scanner._bf_open(state, "AAA", "заметка", 0.05)
check(m == [] and keys("virtual_BFM").count("AAA") == 1, "повтор AAA — ни новых сделок, ни сообщений")

# 5. выход по времени: строка 🏦ᵐ — к сообщению 🏦
trader._virt_scan = lambda t: None
real_time = time.time
time.time = lambda: real_time() + 169 * 3600
msgs = trader.virt_manage(state)
time.time = real_time
aaa = [x for x in msgs if "AAA" in x]
check(len(aaa) == 1 and "🏦³" in aaa[0] and "🏦ᵐ" in aaa[0], f"закрытие AAA — одно сообщение с 🏦³ и 🏦ᵐ ({len(aaa)})")

# 6. /export
HOME = os.path.join(TMP, "home", "someuser"); os.makedirs(HOME)
os.environ["HOME"] = HOME
scanner.EXPORT_FILE = os.path.join(HOME, "margin_export_signals.txt")
SENT, FILES = [], []
scanner.send = lambda cid, text: SENT.append((cid, text))
scanner.tg_file = lambda cid, name, data, caption="": (FILES.append((cid, name, data, caption)), {"ok": True})[1]


def tool(body):
    p = os.path.join(TMP, "tool.py")
    open(p, "w").write(body)
    scanner.EXPORT_TOOL = p


def wait():
    for _ in range(100):
        if scanner._exp["proc"] is None or scanner._exp["proc"].poll() is not None:
            return
        time.sleep(0.05)


tool("import os, time\ntime.sleep(0.3)\nopen(os.path.expanduser('~/margin_export_signals.txt'), 'w')"
     ".write('EXPORT-SIG v3 | папка ' + os.path.expanduser('~') + '/projects/margin_call-live/bot\\nстрока 2\\n')\n")
r1 = scanner.export_start(111)
r2 = scanner.export_start(111)
check("Собираю выгрузку" in r1 and "уже собирается" in r2, "/export: запуск и повторная команда во время сборки")
wait(); scanner.export_check()
check(len(FILES) == 1 and FILES[0][0] == 111 and FILES[0][1] == "margin_export_signals.txt", "файл отправлен в чат команды")
data = FILES[0][2].decode()
check("someuser" not in data and "папка ~/projects/margin_call-live/bot" in data, "путь к домашней папке скрыт (имени пользователя нет)")
check(scanner._exp["proc"] is None, "после отправки выгрузка снова свободна")

tool("import sys\nsys.exit(3)\n")
scanner.export_start(222); wait(); scanner.export_check()
check(any(c == 222 and "не получилась (код завершения 3)" in t for c, t in SENT), "ошибка выгрузки — сообщение с кодом")

tool("import time\ntime.sleep(30)\n")
scanner.EXPORT_MAX_S = 0.5
scanner.export_start(333); time.sleep(0.8); scanner.export_check()
check(any(c == 333 and "не уложилась" in t for c, t in SENT) and scanner._exp["proc"] is None, "дольше лимита — остановлена")

os.remove(scanner.EXPORT_TOOL)
check("нет tools/export_signals.py" in scanner.export_start(444), "нет файла инструмента — понятный ответ")

print("\nИтог:", "все проверки прошли" if not fails else f"не прошло {len(fails)}: " + "; ".join(fails))
sys.exit(1 if fails else 0)
