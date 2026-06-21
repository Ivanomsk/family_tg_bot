import shutil
from datetime import datetime
from pathlib import Path

from repositories.vpn_repository import (
    load_vpn_db,
    save_vpn_db,
)

from config import BACKUP_DIR, VPN_DIR
from utils.logger import standard_logger, audit_logger

logger = standard_logger
def delete_expired_vpn():
    """
    Помечает истекшие VPN-конфиги как неактивные и перемещает их папки в backups.
    ✅ Пропускает бессрочные конфиги.
    
    Returns:
        int: Количество удалённых конфигов
    """
    db = load_vpn_db()
    now = datetime.now()
    deleted_count = 0
    updated = False
    
    for config_hash, config_data in list(db.items()):
        # Пропускаем уже неактивные
        if not config_data.get('active', True):
            continue
        
        # ✅ ПРОПУСКАЕМ БЕССРОЧНЫЕ
        if config_data.get('permanent', False):
            continue
        
        expires_at_str = config_data.get('expires_at')
        if not expires_at_str:
            continue
        
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at < now:
                # Помечаем как неактивный
                db[config_hash]['active'] = False
                db[config_hash]['expired_at'] = now.isoformat()
                updated = True
                deleted_count += 1
                
                username = config_data.get('username')
                if username:
                    user_dir = Path(VPN_DIR) / username
                    if user_dir.exists():
                        backup_name = f"expired_{username}_{now.strftime('%Y%m%d_%H%M%S')}"
                        backup_path = Path(BACKUP_DIR) / backup_name
                        shutil.move(str(user_dir), str(backup_path))
                        logger.info(f"🗑️ Конфиг {username} перемещен в backups/{backup_name}")
                
                audit_logger.info(
                    f"ACTION:DELETE_EXPIRED_VPN | USER:{config_data.get('user_id')} | "
                    f"CONFIG:{config_hash[:20]}... | EXPIRED_AT:{expires_at_str}"
                )
                
        except ValueError:
            continue
    
    if updated:
        save_vpn_db(db)
        logger.info(f"🗑️ Всего удалено {deleted_count} истекших VPN-конфигов")
    
    return deleted_count


def get_user_vpn_configs(user_id: int) -> list:
    """
    Возвращает список активных конфигов пользователя.
    
    Returns:
        list: Список словарей с полями: hash, username, expires_at, days_left, permanent
    """
    db = load_vpn_db()
    now = datetime.now()
    result = []
    
    for config_hash, config_data in db.items():
        if config_data.get('user_id') == user_id and config_data.get('active', True):
            expires_at_str = config_data.get('expires_at')
            days_left = None
            is_permanent = config_data.get('permanent', False)
            if expires_at_str and not is_permanent:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str)
                    days_left = (expires_at - now).days
                except ValueError:
                    pass
            
            result.append({
                'hash': config_hash,
                'username': config_data.get('username', 'unknown'),
                'expires_at': expires_at_str,
                'days_left': days_left,
                'ip': config_data.get('ip'),
                'issued_at': config_data.get('issued_at'),
                'permanent': is_permanent
            })
    
    return result


def get_expired_vpn_list() -> list:
    """
    Возвращает список истекших конфигов (без бессрочных).
    
    Returns:
        list: Список словарей с полями: hash, username, user_id, expires_at
    """
    db = load_vpn_db()
    now = datetime.now()
    result = []
    
    for config_hash, config_data in db.items():
        if not config_data.get('active', True):
            continue
        
        # ✅ ПРОПУСКАЕМ БЕССРОЧНЫЕ
        if config_data.get('permanent', False):
            continue
        
        expires_at_str = config_data.get('expires_at')
        if not expires_at_str:
            continue
        
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at < now:
                result.append({
                    'hash': config_hash,
                    'username': config_data.get('username'),
                    'user_id': config_data.get('user_id'),
                    'expires_at': expires_at_str
                })
        except ValueError:
            continue
    
    return result