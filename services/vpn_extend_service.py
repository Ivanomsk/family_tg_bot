from datetime import datetime, timedelta

from repositories.vpn_repository import (
    load_vpn_db,
    save_vpn_db,
)
def extend_vpn_config(user_id: int, config_hash: str, days: int = 30):
    """
    Продлевает VPN-конфиг на N дней БЕЗ пересоздания.
    
    Args:
        user_id: Telegram ID пользователя
        config_hash: Хеш (public_key) конфига
        days: На сколько дней продлить (по умолчанию 30)
    
    Returns:
        (success: bool, result: str или datetime)
    """
    db = load_vpn_db()
    
    if config_hash not in db:
        return False, "Конфиг не найден"
    
    config_data = db[config_hash]
    
    # Проверяем, принадлежит ли конфиг этому пользователю
    if config_data.get('user_id') != user_id:
        return False, "Это не ваш конфиг"
    
    # Проверяем, активен ли конфиг
    if not config_data.get('active', True):
        return False, "Конфиг неактивен (был отозван)"
    
    # ✅ Если бессрочный — не продлеваем
    if config_data.get('permanent', False):
        return False, "Бессрочный конфиг не требует продления"
    
    expires_at_str = config_data.get('expires_at')
    if not expires_at_str:
        return False, "Дата истечения не найдена"
    
    try:
        current_expires = datetime.fromisoformat(expires_at_str)
    except ValueError:
        return False, "Некорректный формат даты"
    
    # Если конфиг уже истёк — продлеваем с сегодняшнего дня
    if current_expires < datetime.now():
        new_expires = datetime.now() + timedelta(days=days)
    else:
        new_expires = current_expires + timedelta(days=days)
    
    # Обновляем дату
    db[config_hash]['expires_at'] = new_expires.isoformat()
    save_vpn_db(db)
    
    logger.info(f"🔄 Продлен конфиг {config_hash[:20]}... для пользователя {user_id} до {new_expires.isoformat()}")
    audit_logger.info(
        f"ACTION:EXTEND_VPN | USER:{user_id} | "
        f"CONFIG:{config_hash[:20]}... | OLD:{expires_at_str} | NEW:{new_expires.isoformat()}"
    )
    
    return True, new_expires


