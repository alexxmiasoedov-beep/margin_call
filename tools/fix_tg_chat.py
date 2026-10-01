"""Починка экспериментального бота (signals_bot.py) после переезда Telegram-группы в супергруппу.

Запуск на сервере одной строкой из любой папки:
  curl -sL https://raw.githubusercontent.com/alexxmiasoedov-beep/margin_call/main/tools/fix_tg_chat.py | python3

Что делает:
 1. находит папку с signals_bot.py в домашнем каталоге;
 2. шлёт тестовое сообщение в обе группы из .env (EXP — сводка, SIG — сигналы);
 3. если группа стала супергруппой, берёт новый номер чата из ответа Telegram
    и вписывает его в .env (старый .env сохраняется как .env.bak);
 4. делает один проход бота с отправкой (signals_bot.py --post) и показывает результат;
 5. показывает задание cron и хвост журнала cron_exp.log.
Токены на экран не выводятся.
"""
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request

home = os.path.expanduser("~")
found = None
for root, dirs, files in os.walk(home):
    dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "__pycache__")]
    if "signals_bot.py" in files:
        found = root
        break
if not found:
    raise SystemExit("signals_bot.py не найден в " + home)
os.chdir(found)
print("Папка бота:", found)
if not os.path.exists(".env"):
    raise SystemExit("В папке нет .env — бот не настроен на отправку")

raw = open(".env").read()
env = {}
for line in raw.splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

changed = False
for t in ("EXP", "SIG"):
    tok, cid = env.get(f"TG_BOT_TOKEN_{t}"), env.get(f"TG_CHAT_ID_{t}")
    name = "сводка (EXP)" if t == "EXP" else "сигналы (SIG)"
    if not tok or not cid:
        print(f"{name}: не задано в .env")
        continue
    data = urllib.parse.urlencode({"chat_id": cid, "text": "проверка связи: бот снова на месте"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data, timeout=20).read()
        print(f"{name}: чат {cid} — работает")
    except urllib.error.HTTPError as e:
        try:
            r = json.loads(e.read().decode())
        except Exception:
            r = {"description": str(e)}
        new = (r.get("parameters") or {}).get("migrate_to_chat_id")
        print(f"{name}: чат {cid} — ошибка: {r.get('description')}")
        if new:
            for line in raw.splitlines():
                if line.strip().startswith(f"TG_CHAT_ID_{t}"):
                    raw = raw.replace(line, f"TG_CHAT_ID_{t}={new}")
            changed = True
            print(f"{name}: новый номер чата {new} — вписываю в .env")
    except Exception as e:
        print(f"{name}: нет связи с Telegram: {e!r}")

if changed:
    shutil.copy(".env", ".env.bak")
    open(".env", "w").write(raw)
    print(".env обновлён, старая версия в .env.bak")

print("\n--- пробный проход бота с отправкой ---")
p = subprocess.run(["python3", "signals_bot.py", "--post"], capture_output=True, text=True, timeout=300)
print("готово, сводка отправлена" if p.returncode == 0 else "ОШИБКА:\n" + (p.stderr or p.stdout)[-1500:])

print("\n--- задание cron ---")
c = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
lines = [l for l in c.stdout.splitlines() if "signals_bot" in l]
print("\n".join(lines) if lines else "НЕТ задания cron для signals_bot.py — бот не будет запускаться сам")

if os.path.exists("cron_exp.log"):
    print("\n--- последние строки cron_exp.log ---")
    print("".join(open("cron_exp.log", errors="replace").readlines()[-12:]))
