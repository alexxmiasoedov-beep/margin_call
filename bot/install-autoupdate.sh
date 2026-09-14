#!/bin/bash
# Однократная установка автообновления на сервере (запускать от root):
#   cd /opt/margin_call && bash bot/install-autoupdate.sh
set -e
DIR=$(cd "$(dirname "$0")/.." && pwd)
sed "s#/opt/margin_call#$DIR#g" "$DIR/bot/margin-autoupdate.service" > /etc/systemd/system/margin-autoupdate.service
cp "$DIR/bot/margin-autoupdate.timer" /etc/systemd/system/margin-autoupdate.timer
chmod +x "$DIR/bot/autoupdate.sh"
systemctl daemon-reload
systemctl enable --now margin-autoupdate.timer
echo "Готово. Автообновление включено, проверка каждые 5 минут."
systemctl list-timers margin-autoupdate.timer --no-pager
