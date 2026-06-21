from config import VPN_DIR
from utils.logger import standard_logger
import os
import re

logger = standard_logger

# ==========================================
# ÂÑÏÎÌÎÃÀÒÅËÜÍÛÅ ÔÓÍÊÖÈÈ
# ==========================================

def get_user_dir(username: str) -> str:
    safe_name = re.sub(r'[^\w\-]', '_', username)
    path = os.path.join(VPN_DIR, safe_name)
    os.makedirs(path, exist_ok=True)
    return path


def get_user_configs(username: str) -> list:
    if not username:
        return []
    user_dir = get_user_dir(username)
    try:
        files = [f for f in os.listdir(user_dir) if f.endswith('.vpn')]
        logger.info(f"Scanning {user_dir}: found {len(files)} files: {files}")
        return sorted(files)
    except Exception as e:
        logger.error(f"Scan error {user_dir}: {e}")
        return []
