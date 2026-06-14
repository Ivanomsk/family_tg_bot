import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "764438696").split(",")]
ALLOWED_CHAT_ID = int(os.getenv("ALLOWED_CHAT_ID", "-1001741127726"))
AUTO_DELETE_DELAY = int(os.getenv("AUTO_DELETE_DELAY", "120"))
PROXY_EXPIRY_DAYS = int(os.getenv("PROXY_EXPIRY_DAYS", "30"))
VPN_EXPIRY_DAYS = int(os.getenv("VPN_EXPIRY_DAYS", "30"))  # Срок VPN конфигов
# ============================================
# ТАЙМЕРЫ АВТОУДАЛЕНИЯ СООБЩЕНИЙ (в секундах)
# Настраиваются через .env, 0 = не удалять
# ============================================
DELETE_DELAY_TEMP = int(os.getenv("DELETE_DELAY_TEMP", "30"))
DELETE_DELAY_USER = int(os.getenv("DELETE_DELAY_USER", "120"))
DELETE_DELAY_PROXY_CARD = int(os.getenv("DELETE_DELAY_PROXY_CARD", "300"))
DELETE_DELAY_ADMIN = int(os.getenv("DELETE_DELAY_ADMIN", "600"))
DELETE_DELAY_NEVER = 0  # Константа — не удалять никогда

DATA_DIR = "bot_data"
VPN_DIR = os.path.join(DATA_DIR, "vpn_configs")
STATS_FILE = os.path.join(DATA_DIR, "stats.json")
USER_PROXIES_FILE = os.path.join(DATA_DIR, "user_proxies.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

for d in [DATA_DIR, VPN_DIR, BACKUP_DIR]:
    os.makedirs(d, exist_ok=True)

def is_allowed(message) -> bool:
    """Проверка доступа пользователя"""
    if message.chat.type == "private":
        return True
    if message.chat.id == ALLOWED_CHAT_ID:
        return True
    return message.from_user.id in ADMIN_IDS

# Максимальное количество хранимых бэкапов
MAX_BACKUPS = int(os.getenv("MAX_BACKUPS", "5"))