from pathlib import Path
import json


VPN_DB_PATH = Path("/opt/durdom-bot/bot_data/vpn_users.json")
VPN_DB_PATH.parent.mkdir(exist_ok=True)


def load_vpn_db():
    """
    Загружает локальную БД VPN пользователей.
    """
    if VPN_DB_PATH.exists():
        with open(VPN_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    return {}


def save_vpn_db(db):
    """
    Сохраняет локальную БД.
    """
    with open(VPN_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(
            db,
            f,
            indent=2,
            ensure_ascii=False
        )
