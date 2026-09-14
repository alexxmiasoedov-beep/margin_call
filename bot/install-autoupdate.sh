#!/bin/bash
# Однократная установка автообновления на сервере:
#   cd <папка репозитория> && bash bot/install-autoupdate.sh
# Ставится туда же, где живёт служба бота margin-scanner: если она пользовательская
# (systemctl --user) — в ~/.config/systemd/user без sudo, иначе в /etc/systemd/system от root.
set -e
DIR=$(cd "$(dirname "$0")/.." && pwd)
chmod +x "$DIR/bot/autoupdate.sh"

if systemctl --user cat margin-scanner >/dev/null 2>&1; then
    SC="systemctl --user"
    UNITS="$HOME/.config/systemd/user"
    mkdir -p "$UNITS"
    if [ "$(id -u)" = 0 ]; then echo "Служба бота пользовательская — запускайте установку без sudo"; exit 1; fi
elif systemctl cat margin-scanner >/dev/null 2>&1; then
    SC="systemctl"
    UNITS="/etc/systemd/system"
    if [ "$(id -u)" != 0 ]; then echo "Служба бота системная — запускайте установку через sudo"; exit 1; fi
else
    echo "Служба margin-scanner не найдена ни у пользователя, ни в системе: сначала установите bot/margin-scanner.service"
    exit 1
fi

sed "s#/opt/margin_call#$DIR#g" "$DIR/bot/margin-autoupdate.service" > "$UNITS/margin-autoupdate.service"
cp "$DIR/bot/margin-autoupdate.timer" "$UNITS/margin-autoupdate.timer"
$SC daemon-reload
$SC reset-failed margin-autoupdate.service 2>/dev/null || true
$SC enable --now margin-autoupdate.timer
if [ "$SC" = "systemctl --user" ]; then
    # чтобы пользовательские службы жили и без открытой сессии
    loginctl enable-linger "$USER" 2>/dev/null || echo "Подсказка: sudo loginctl enable-linger $USER — чтобы службы работали после выхода из SSH"
fi
echo "Готово. Автообновление включено ($SC), проверка каждые 5 минут."
$SC list-timers margin-autoupdate.timer --no-pager
