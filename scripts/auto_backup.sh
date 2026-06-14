#!/bin/bash

# Скрипт автоматического резервного копирования DurdomVPN26_Bot
BOT_DIR="/opt/durdom-bot"
BACKUP_DIR="$BOT_DIR/bot_data/backups"
LOG_FILE="$BOT_DIR/bot_data/logs/backup.log"
MAX_BACKUPS=7

# 1. Безопасное чтение переменных из .env (игнорируем комментарии и удаляем \r)
if [ -f "$BOT_DIR/.env" ]; then
    BOT_TOKEN=$(grep '^BOT_TOKEN=' "$BOT_DIR/.env" | cut -d '=' -f2- | tr -d '\r')
    ADMIN_IDS=$(grep '^ADMIN_IDS=' "$BOT_DIR/.env" | cut -d '=' -f2- | tr -d '\r')
    NOTIFY_CHAT_ID=$(echo "$ADMIN_IDS" | cut -d',' -f1 | tr -d '\r')
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ❌ Файл .env не найден!" | tee -a "$LOG_FILE"
    exit 1
fi

mkdir -p "$BACKUP_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log "🚀 Начало автоматического бэкапа"

TIMESTAMP=$(date '+%Y-%m-%d_%H-%M')
ARCHIVE_NAME="auto-backup-$TIMESTAMP.tar.gz"
ARCHIVE_PATH="$BACKUP_DIR/$ARCHIVE_NAME"

cd "$BOT_DIR" || { log "❌ Не удалось перейти в директорию $BOT_DIR"; exit 1; }

# 2. Создание архива
tar -czf "$ARCHIVE_PATH" \
    main.py config.py requirements.txt .env .gitignore \
    handlers utils database states keyboards \
    bot_data/stats.json bot_data/user_proxies.json bot_data/vpn_configs \
    bot_data/last_notifications.json 2>/dev/null

if [ $? -eq 0 ]; then
    SIZE=$(du -h "$ARCHIVE_PATH" | cut -f1)
    log "✅ Бэкап создан: $ARCHIVE_NAME ($SIZE)"
    
    # 3. Отправка уведомления в Telegram через Python (гарантированно работает без curl)
    python3 -c "
import urllib.request
import urllib.parse

token = '$BOT_TOKEN'
chat_id = '$NOTIFY_CHAT_ID'
msg = '✅ <b>Автобэкап выполнен успешно!</b>\n\n📦 Файл: <code>$ARCHIVE_NAME</code>\n💾 Размер: $SIZE\n🕐 Время: $(date '+%H:%M:%S')'

url = f'https://api.telegram.org/bot{token}/sendMessage'
data = urllib.parse.urlencode({
    'chat_id': chat_id,
    'text': msg,
    'parse_mode': 'HTML'
}).encode('utf-8')

try:
    req = urllib.request.Request(url, data=data, method='POST')
    urllib.request.urlopen(req)
except Exception as e:
    pass
"
    log "📢 Уведомление админу отправлено"
else
    log "❌ Ошибка создания бэкапа"
    exit 1
fi

# 4. Удаление старых бэкапов (оставляем только MAX_BACKUPS последних)
# tr -d ' \n\r' гарантирует, что число будет чистым, без пробелов и скрытых символов
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/auto-backup-*.tar.gz 2>/dev/null | wc -l | tr -d ' \n\r')

if [ "$BACKUP_COUNT" -gt "$MAX_BACKUPS" ]; then
    DELETE_COUNT=$((BACKUP_COUNT - MAX_BACKUPS))
    log "🗑 Удаляем $DELETE_COUNT старых бэкапов"
    
    ls -1t "$BACKUP_DIR"/auto-backup-*.tar.gz | tail -n "$DELETE_COUNT" | while read -r old_backup; do
        rm -f "$old_backup"
        log "🗑 Удалён: $(basename "$old_backup")"
    done
else
    log "📊 Бэкапов: $BACKUP_COUNT/$MAX_BACKUPS — очистка не требуется"
fi

log "✅ Автоматический бэкап завершён"