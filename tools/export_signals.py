"""Выгрузка сигналов и виртуальных журналов бота — для сверки с пересчётом по архиву Binance.

Запуск на сервере одной строкой из любой папки:
  curl -sL https://raw.githubusercontent.com/alexxmiasoedov-beep/margin_call/main/tools/export_signals.py | python3

Печатает: настройки правил (без ключей и токена), все сделки виртуальных журналов из state.json
(время и цена входа = момент сигнала у бота), строки журнала службы margin-scanner с 29.09
(сигналы, новые правила, пропуски, перезапуски) и реальные сделки. Ничего не меняет, ордеров не ставит.
Копия вывода сохраняется в ~/margin_export_signals.txt.
"""
import datetime
import json
import os
import re
import subprocess
import time

home = os.path.expanduser("~")
SINCE = "2026-09-29"
SAFE = ("CHANNEL", "MIN_RUN_H", "GAP_MIN", "PUMP_MIN", "PUMP_MAX", "COOLDOWN_H", "TRADE_MODE", "POSITION_USDT", "LEVERAGE",
        "SL_PCT", "TP_PCT", "HOLD_H", "MAX_POSITIONS", "LSR_MAX", "DUMP_RULE", "DUMP_BR_MIN", "STOP_PAUSE_H", "FUND_EXIT",
        "POLL_SEC", "STATE_FILE")                     # только настройки правил — ключи и токен не печатаются
JOURNALS = (("virtual", "📓"), ("virtual_fund", "📗"), ("virtual_1525", "📘"), ("virtual_1520", "📕"), ("virtual_620", "📙"))
OWN = (("virtual_D", "🟦"), ("virtual_P", "🟧"))
LOG_PAT = re.compile(r"СИГНАЛ|НОВОЕ ПРАВИЛО|СМЕНА ИНТЕРВАЛА|РЕАЛЬНАЯ|БУМАЖНАЯ|⏭|пропуск|не открыта|закрыт шорт|ошибка|проход занял|"
                     r"канал недоступен|Binance OK|торговля выключена|Убраны|Started|Stopped|Stopping|Main process exited|Scheduled restart")
out = []


def p(line=""):
    out.append(line)
    print(line, flush=True)


def fmt(ts, sec=True):
    if not ts:
        return "—"
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%d.%m %H:%M:%S" if sec else "%d.%m %H:%M")


def short(reason):
    reason = str(reason or "")
    return "время" if reason.startswith("выход по времени") else reason[:60]


def read_env(path):
    env = {}
    try:
        for line in open(path):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return env


def run(cmd, timeout=120):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception:
        return ""


# ---------------------------------------------------------------- где бот и его настройки
bot = next((c for c in (os.path.join(home, "projects", "margin_call-live", "bot"), "/opt/margin_call/bot")
            if os.path.exists(os.path.join(c, "trader.py"))), None)
if not bot:
    for root, dirs, files in os.walk(home):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__")]
        if "trader.py" in files and "scanner.py" in files and os.path.exists(os.path.join(root, "state.json")):
            bot = root
            break
if not bot:
    raise SystemExit("папка бота со state.json не найдена")
env_files = [os.path.join(home, ".config", "margin-call.env")]
for sc in (["systemctl", "--user"], ["systemctl"]):
    for line in run(sc + ["show", "-p", "EnvironmentFiles", "margin-scanner"], 15).splitlines():
        path = line.split("=", 1)[-1].split(" (")[0].strip()
        if path and path not in env_files:
            env_files.append(path)
env_files.append(os.path.join(bot, "..", ".env"))
env = {}
for f in env_files:
    env.update(read_env(f))
state_path = env.get("STATE_FILE") or "state.json"
state_path = state_path if os.path.isabs(state_path) else os.path.join(bot, state_path)
state = json.load(open(state_path))
commit = run(["git", "-C", bot, "log", "-1", "--format=%h %cd", "--date=format:%d.%m %H:%M"], 15).strip()
p(f"EXPORT-SIG v1 | папка {bot} | код {commit or '?'} | сейчас {fmt(datetime.datetime.now().timestamp())} UTC (всё время ниже — UTC)")
p("настройки: " + ", ".join(f"{k}={env[k]}" for k in SAFE if k in env))
p("изменены из чата (/set): " + json.dumps(state.get("params") or {}, ensure_ascii=False))

# ---------------------------------------------------------------- виртуальные журналы: одна строка на сигнал
p()
p("# ВИРТУАЛЬНЫЕ ЖУРНАЛЫ")
for key, icon in JOURNALS + OWN:
    v = state.get(key) or {}
    p(f"{icon} с {fmt(v.get('started'))}, баланс {v.get('balance', 20):.2f} с {fmt(v.get('bal_since'))}, сделок {len(v.get('trades', []))}")
groups = {}
for key, icon in JOURNALS:
    for t in (state.get(key) or {}).get("trades", []):
        groups.setdefault((round(t["opened"]), t["sym"]), {})[icon] = t
p("вход | сигнал | по журналам: тейк/стоп исход время-выхода итог фандинг")
for (op, sym), d in sorted(groups.items()):
    first = next(iter(d.values()))
    fh = first.get("fh_entry")
    row = [f"{fmt(op)} {sym} {first.get('rule', '')} вход {first['entry']:.6g}" + (f" ф/ч {fh * 100:+.3f}%" if fh is not None else "")]
    for key, icon in JOURNALS:
        t = d.get(icon)
        if not t:
            row.append(f"{icon} —")
            continue
        tp = f"{t['tp_pct']:g}" if t.get("tp_pct") else "—"
        res = (f"{short(t.get('reason'))} {fmt(t['closed'], False)} {t.get('pnl_usdt', 0):+.2f} ф{t.get('fund_usdt', 0):+.2f}"
               if t.get("closed") else "открыта")
        row.append(f"{icon} {tp}/{t.get('sl_pct', 25):g} {res}")
    p(" | ".join(row))
for key, icon in OWN:
    for t in sorted((state.get(key) or {}).get("trades", []), key=lambda t: t["opened"]):
        res = (f"{short(t.get('reason'))} {fmt(t['closed'], False)} {t.get('pnl_usdt', 0):+.2f} ф{t.get('fund_usdt', 0):+.2f}"
               if t.get("closed") else "открыта")
        p(f"{icon} {fmt(t['opened'])} {t['sym']} вход {t['entry']:.6g} {t.get('tp_pct', 0):g}/{t.get('sl_pct', 0):g} {res} | {t.get('note', '')}")

# ---------------------------------------------------------------- реальные сделки
p()
p("# РЕАЛЬНЫЕ СДЕЛКИ (бот хранит 30 дней)")
for t in sorted(state.get("trades", []), key=lambda t: t["opened"]):
    res = f"{fmt(t['closed'], False)} {short(t.get('reason'))} {t.get('pnl_usdt', 0):+.2f}" if t.get("closed") else "открыта"
    p(f"{fmt(t['opened'])} {t['sym']} {t.get('rule', '')} {t.get('mode', '')} вход {t['entry']:.6g} маржа {t.get('margin', 0):g} → {res}")

# ---------------------------------------------------------------- журнал службы: сигналы, пропуски, перезапуски
p()
p(f"# ЖУРНАЛ СЛУЖБЫ с {SINCE}")
lines, scans, partial, deadline = [], [], False, time.time() + 150
pat = LOG_PAT.pattern + "|постов"
print("читаю журнал службы — до 2–3 минут…", flush=True)
for cmd in (["journalctl", "--user", "-u", "margin-scanner"], ["journalctl", "--user-unit", "margin-scanner"],
            ["journalctl", "-u", "margin-scanner"]):
    for grep in (["-g", pat], []):                   # -g фильтрует внутри journalctl; старые версии его не знают
        left = int(deadline - time.time())
        if left <= 5:
            break
        try:                                         # timeout обрывает journalctl, если журнал огромный или он завис
            pr = subprocess.Popen(["timeout", str(left)] + cmd + ["--since", SINCE, "--utc", "-o", "short-iso", "--no-pager", "-q"] + grep,
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace")
        except OSError:
            break
        got, sc = [], []
        for ln in pr.stdout:
            if "постов" in ln:
                sc.append(ln[:19])                   # только время прохода — для поиска простоев
            elif LOG_PAT.search(ln) and "виртуально" not in ln:
                got.append(ln)
        partial = pr.wait() == 124                   # 124 — journalctl остановлен по времени
        if got or sc:
            lines, scans = got, sc
            break
    if lines or scans:
        break
if partial:
    p("⚠️ журнал прочитан не полностью — не уложился в 2,5 мин")
for ln in lines:
    m = re.match(r"^\d{4}-(\d\d)-(\d\d)T(\d\d:\d\d:\d\d)\S*\s+\S+\s+[^:]+:\s?(.*)$", ln)
    if not m:
        continue
    msg = re.sub(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ", "", m.group(4))
    if "Binance OK" in msg or "торговля выключена" in msg:
        msg = "старт бота"
    p(f"{m.group(2)}.{m.group(1)} {m.group(3)} {msg[:400]}")
gaps = []
for a, b in zip(scans, scans[1:]):
    try:
        ta, tb = (datetime.datetime.strptime(x, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).timestamp() for x in (a, b))
    except ValueError:
        continue
    if tb - ta > 600:
        gaps.append(f"{fmt(ta, False)} → {fmt(tb, False)} ({(tb - ta) / 3600:.1f} ч)")
if scans:
    p(f"проходов сканера: {len(scans)}; простои дольше 10 мин: " + ("; ".join(gaps) if gaps else "нет"))
if not lines:
    p("журнал службы недоступен или пуст — ниже сигналы из state.json (бот хранит их 72 ч)")
    for a in sorted(state.get("alerts", []), key=lambda a: a["ts"]):
        p(f"{fmt(a['ts'])} {a.get('rule')} {a['sym']} цена {a.get('price')} 4ч {a.get('b4h')} серия {a.get('run_h')} B/R {a.get('br')} "
          f"LSR {a.get('lsr')} от пика {a.get('from_peak')} риск {a.get('risk')}")

dest = os.path.join(home, "margin_export_signals.txt")
with open(dest, "w") as f:
    f.write("\n".join(out) + "\n")
print(f"\nкопия: {dest} ({len(out)} строк)")
