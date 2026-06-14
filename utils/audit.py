import logging
from datetime import datetime
from config import ADMIN_IDS

logger = logging.getLogger("audit")

def log_admin_action(admin_id: int, action: str, details: str = ""):
    """
    Логирует действие администратора
    
    Args:
        admin_id: ID администратора
        action: Тип действия (BACKUP, CLEAR_USER, DELETE_CONFIG и т.д.)
        details: Дополнительная информация
    """
    # Проверяем что это действительно админ
    if admin_id not in ADMIN_IDS:
        logger.warning(f"🚨 ПОПЫТКА НЕАВТОРИЗОВАННОГО ДЕЙСТВИЯ: User {admin_id} -> {action}")
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"👨‍💼 ADMIN {admin_id} | {action} | {details} | {timestamp}"
    
    logger.info(log_message)

def log_suspicious_activity(user_id: int, action: str, reason: str):
    """Логирует подозрительную активность"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"🚨 ПОДОЗРИТЕЛЬНО: User {user_id} | {action} | {reason} | {timestamp}"
    
    logger.warning(log_message)
