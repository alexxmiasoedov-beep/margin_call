#!/bin/bash
# Автообновление бота из GitHub. Запускается таймером margin-autoupdate.timer каждые 5 минут:
# тянет main, если изменился код бота — обновляет файлы, перезапускает службу и пишет в Telegram.
# Файл состояния bot/state.json никогда не трогается.
set -u
cd "$(dirname "$0")/.." || exit 1
# Бот может стоять как пользовательская служба (systemctl --user) или системная
if systemctl --user cat margin-scanner >/dev/null 2>&1; then SC="systemctl --user"; else SC="systemctl"; fi
git fetch -q origin main || { echo "autoupdate: git fetch не удался"; exit 1; }
# Файлы кода, которые обновляем (только те, что есть в origin/main)
CODE=""
for f in bot/scanner.py bot/trader.py bot/autoupdate.sh bot/margin-scanner.service; do
    git cat-file -e "origin/main:$f" 2>/dev/null && CODE="$CODE $f"
done
if git diff --quiet HEAD origin/main -- $CODE; then
    exit 0
fi

OLD=$(git rev-parse --short HEAD)
# Быстрая перемотка, а если мешают локальные правки (state.json) — забираем только файлы кода.
if ! git merge -q --ff-only origin/main 2>/dev/null; then
    git checkout -q origin/main -- $CODE || { echo "autoupdate: не удалось обновить файлы"; exit 1; }
    git update-ref HEAD origin/main
    git reset -q -- $CODE
fi
NEW=$(git rev-parse --short HEAD)
SUBJ=$(git log -1 --format=%s origin/main)
python3 -c "import ast; ast.parse(open('bot/scanner.py').read()); ast.parse(open('bot/trader.py').read())" \
    || { echo "autoupdate: синтаксическая ошибка в новом коде, служба не перезапущена"; exit 1; }

$SC restart margin-scanner || { echo "autoupdate: не удалось перезапустить margin-scanner ($SC)"; exit 1; }
echo "autoupdate: $OLD -> $NEW: $SUBJ"

# Сообщение в Telegram всем подписчикам бота
TOKEN=$(grep -E '^TG_BOT_TOKEN=' .env 2>/dev/null | cut -d= -f2- | tr -d '"'"' ")
STATE=$(grep -E '^STATE_FILE=' .env 2>/dev/null | cut -d= -f2- | tr -d '"'"' ")
STATE=${STATE:-state.json}; [[ "$STATE" = /* ]] || STATE="bot/$STATE"
[ -n "$TOKEN" ] && [ -f "$STATE" ] && python3 - "$TOKEN" "$STATE" "$NEW" "$SUBJ" <<'PY'
import json, sys, urllib.parse, urllib.request
token, state, new, subj = sys.argv[1:]
try:
    subs = json.load(open(state)).get("subscribers", [])
except Exception:
    subs = []
for chat in subs:
    data = urllib.parse.urlencode({"chat_id": chat, "text": f"🔄 Бот обновлён до {new} и перезапущен:\n{subj}"}).encode()
    try:
        urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=15)
    except Exception as e:
        print("autoupdate: telegram:", e)
PY
exit 0
