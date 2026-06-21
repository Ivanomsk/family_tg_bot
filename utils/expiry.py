import os
import json
from datetime import datetime, timedelta
from config import VPN_DIR, USER_PROXIES_FILE, VPN_EXPIRY_DAYS, PROXY_EXPIRY_DAYS
from database.storage import load_json
from utils.logger import standard_logger

logger = standard_logger


# ==========================================
# VPN
# ==========================================

def get_vpn_config_age(username: str, filename: str) -> dict:
    try:
        user_dir = os.path.join(VPN_DIR, username)
        file_path = os.path.join(user_dir, filename)
        if not os.path.exists(file_path):
            return {"status": "not_found", "days_left": None}
        
        import re
        match = re.search(r'(\d{2})\.(\d{2})\.vpn', filename)
        if match:
            day, month = int(match.group(1)), int(match.group(2))
            year = datetime.now().year
            expires = datetime(year, month, day)
            if expires < datetime.now():
                expires = expires.replace(year=year + 1)
            days_left = (expires - datetime.now()).days
        else:
            days_left = 30
        
        if days_left < 0:
            return {"status": "expired", "days_left": days_left}
        elif days_left <= 3:
            return {"status": "expiring_soon", "days_left": days_left}
        else:
            return {"status": "active", "days_left": days_left}
            
    except Exception as e:
        logger.error(f"Ошибка получения возраста конфига {filename}: {e}")
        return {"status": "unknown", "days_left": None}


def check_all_vpn_expiry():
    """Проверяет все VPN конфиги на истечение (из vpn_users.json)"""
    from repositories.vpn_repository import load_vpn_db
    db = load_vpn_db()
    expired = []
    expiring = []
    now = datetime.now()
    
    for public_key, data in db.items():
        username = data.get('username', 'unknown')
        active = data.get('active', True)
        permanent = data.get('permanent', False)
        expires_at_str = data.get('expires_at')
        
        # Пропускаем неактивные и бессрочные
        if not active:
            continue
        if permanent:
            continue
        if not expires_at_str:
            continue
        
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            days_left = (expires_at - now).days
            
            if days_left < 0:
                expired.append({
                    'username': username,
                    'filename': f"{username}.vpn",
                    'days_left': days_left
                })
            elif days_left <= 3:
                expiring.append({
                    'username': username,
                    'filename': f"{username}.vpn",
                    'days_left': days_left
                })
        except ValueError:
            continue
    
    return expired, expiring


# ==========================================
# ПРОКСИ
# ==========================================

def get_proxy_age(user_id: int, proxy_name: str) -> dict:
    try:
        user_proxies = load_json(USER_PROXIES_FILE, {})
        proxies = user_proxies.get(str(user_id), {}).get("proxies", [])
        
        for proxy in proxies:
            if proxy.get("name") == proxy_name:
                if proxy.get('permanent', False):
                    return {"status": "permanent", "days_left": None}
                
                issued_at = proxy.get("issued_at")
                if not issued_at:
                    return {"status": "unknown", "days_left": None}
                
                issued_date = datetime.fromisoformat(issued_at)
                expires_date = issued_date + timedelta(days=PROXY_EXPIRY_DAYS)
                days_left = (expires_date - datetime.now()).days
                
                if days_left < 0:
                    return {"status": "expired", "days_left": days_left}
                elif days_left <= 3:
                    return {"status": "expiring_soon", "days_left": days_left}
                else:
                    return {"status": "active", "days_left": days_left}
        
        return {"status": "not_found", "days_left": None}
        
    except Exception as e:
        logger.error(f"Ошибка получения возраста прокси {proxy_name}: {e}")
        return {"status": "unknown", "days_left": None}


def check_all_proxy_expiry():
    """Проверяет все прокси на истечение (из user_proxies.json)"""
    from database.storage import load_json
    user_proxies = load_json(USER_PROXIES_FILE, {})
    expired = []
    expiring = []
    now = datetime.now()
    
    for user_id_str, data in user_proxies.items():
        user_id = int(user_id_str)
        proxies = data.get("proxies", [])
        
        for proxy in proxies:
            proxy_name = proxy.get("name")
            if not proxy_name:
                continue
            
            # Пропускаем бессрочные
            if proxy.get('permanent', False):
                continue
            
            issued_at = proxy.get("issued_at")
            if not issued_at:
                continue
            
            try:
                issued_date = datetime.fromisoformat(issued_at)
                expires_date = issued_date + timedelta(days=PROXY_EXPIRY_DAYS)
                days_left = (expires_date - now).days
                
                if days_left < 0:
                    expired.append({
                        'user_id': user_id,
                        'proxy_name': proxy_name,
                        'days_left': days_left
                    })
                elif days_left <= 3:
                    expiring.append({
                        'user_id': user_id,
                        'proxy_name': proxy_name,
                        'days_left': days_left
                    })
            except ValueError:
                continue
    
    return expired, expiring


def get_proxy_expiry_date(user_id: int, proxy_name: str) -> str:
    try:
        user_proxies = load_json(USER_PROXIES_FILE, {})
        proxies = user_proxies.get(str(user_id), {}).get("proxies", [])
        
        for proxy in proxies:
            if proxy.get("name") == proxy_name:
                if proxy.get('permanent', False):
                    return "♾️ Бессрочный"
                
                issued_at = proxy.get("issued_at")
                if not issued_at:
                    return "не указана"
                
                issued_date = datetime.fromisoformat(issued_at)
                expires_date = issued_date + timedelta(days=PROXY_EXPIRY_DAYS)
                return expires_date.strftime('%d.%m.%Y')
        
        return "не указана"
        
    except Exception as e:
        logger.error(f"Ошибка получения даты истечения прокси {proxy_name}: {e}")
        return "не указана"


def is_proxy_expired(user_id: int, proxy_name: str) -> bool:
    try:
        user_proxies = load_json(USER_PROXIES_FILE, {})
        proxies = user_proxies.get(str(user_id), {}).get("proxies", [])
        
        for proxy in proxies:
            if proxy.get("name") == proxy_name:
                if proxy.get('permanent', False):
                    return False
                
                issued_at = proxy.get("issued_at")
                if not issued_at:
                    return False
                
                issued_date = datetime.fromisoformat(issued_at)
                expires_date = issued_date + timedelta(days=PROXY_EXPIRY_DAYS)
                return expires_date < datetime.now()
        
        return False
        
    except Exception as e:
        logger.error(f"Ошибка проверки истечения прокси {proxy_name}: {e}")
        return False
