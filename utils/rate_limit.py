import time
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# Хранилище действий пользователей: {user_id_command: [timestamp1, timestamp2, ...]}
user_actions = defaultdict(list)

# Настройки лимитов по командам (вызовов в минуту)
RATE_LIMITS = {
    "vpn": 10,              # /vpn — 10 раз в минуту
    "my_proxy": 10,         # /my_proxy — 10 раз в минуту
    "request_proxy": 3,     # /request_proxy — 3 раза в минуту
    "backup": 2,            # /backup — 2 раза в минуту
    "default": 20,          # остальные команды — 20 раз в минуту
}

def is_rate_limited(user_id: int, command: str) -> tuple[bool, int]:
    """
    Проверяет, превышен ли лимит вызовов команды.
    
    Возвращает:
        (is_limited: bool, retry_after: int) — 
        is_limited=True если лимит превышен,
        retry_after — секунды до сброса лимита
    """
    now = time.time()
    key = f"{user_id}_{command}"
    
    # Получаем лимит для команды
    limit = RATE_LIMITS.get(command, RATE_LIMITS["default"])
    
    # Удаляем записи старше 60 секунд
    user_actions[key] = [
        ts for ts in user_actions[key] 
        if now - ts < 60
    ]
    
    # Проверяем лимит
    if len(user_actions[key]) >= limit:
        # Вычисляем время до сброса (самая старая запись + 60 сек)
        oldest = min(user_actions[key])
        retry_after = int(60 - (now - oldest)) + 1
        logger.warning(f"️ Rate limit: User {user_id} превысил лимит {command} ({limit}/мин)")
        return True, retry_after
    
    # Записываем действие
    user_actions[key].append(now)
    return False, 0

def get_usage_stats(user_id: int, command: str) -> dict:
    """Получить статистику использования команды пользователем"""
    key = f"{user_id}_{command}"
    now = time.time()
    
    # Активные действия за последнюю минуту
    active = [ts for ts in user_actions[key] if now - ts < 60]
    
    limit = RATE_LIMITS.get(command, RATE_LIMITS["default"])
    
    return {
        "used": len(active),
        "limit": limit,
        "remaining": max(0, limit - len(active)),
        "reset_in": 60 - int(now - min(active)) if active else 0
    }
