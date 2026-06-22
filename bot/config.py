import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env из корня проекта
load_dotenv()

BASE_DIR = Path(__file__).parent.parent

# 🟢 ТЕПЕРЬ ПУТИ БЕРУТСЯ ИЗ .ENV (а не вычисляются)
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "bot_data")))
LOG_DIR = Path(os.getenv("LOG_DIR", str(BASE_DIR / "logs")))

# Создаём папки, если их нет
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Админы
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# Лимиты и сроки
VPN_EXPIRY_DAYS = int(os.getenv("VPN_EXPIRY_DAYS", 30))
PROXY_EXPIRY_DAYS = int(os.getenv("PROXY_EXPIRY_DAYS", 30))
PROXY_REQUEST_LIMIT = int(os.getenv("PROXY_REQUEST_LIMIT", 50))

# ⏰ ТАЙМЕРЫ АВТОУДАЛЕНИЯ
DELETE_DELAY_TEMP = int(os.getenv("DELETE_DELAY_TEMP", 30))
DELETE_DELAY_USER = int(os.getenv("DELETE_DELAY_USER", 120))
DELETE_DELAY_PROXY_CARD = int(os.getenv("DELETE_DELAY_PROXY_CARD", 300))
DELETE_DELAY_ADMIN = int(os.getenv("DELETE_DELAY_ADMIN", 600))

# 🌐 ВЕБ-НАСТРОЙКИ
WEB_PASSWORD = os.getenv("WEB_PASSWORD")
WEB_PORT = int(os.getenv("WEB_PORT", 5050))
WEB_DOMAIN = os.getenv("WEB_DOMAIN")

# 🔐 SSH (для генерации VPN)
VPN_SSH_HOST = os.getenv("VPN_SSH_HOST")
VPN_SSH_PORT = int(os.getenv("VPN_SSH_PORT", 22))
VPN_SSH_USER = os.getenv("VPN_SSH_USER")
VPN_SSH_KEY_PATH = os.getenv("VPN_SSH_KEY_PATH")
