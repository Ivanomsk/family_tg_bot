import os
from datetime import datetime
from config import VPN_DIR, VPN_EXPIRY_DAYS, USER_PROXIES_FILE, PROXY_EXPIRY_DAYS
from database.storage import load_json

def get_vpn_config_age(username: str, filename: str) -> dict:
    """Получить возраст VPN конфига"""
    user_dir = os.path.join(VPN_DIR, username)
    file_path = os.path.join(user_dir, filename)
    
    if not os.path.exists(file_path):
        return {"days": 0, "status": "not_found"}
    
    # Используем дату создания файла
    created = datetime.fromtimestamp(os.path.getctime(file_path))
    days_since = (datetime.now() - created).days
    days_left = VPN_EXPIRY_DAYS - days_since
    
    if days_left < 0:
        status = "expired"
    elif days_left <= 7:
        status = "expiring_soon"
    else:
        status = "active"
    
    return {
        "days": days_since,
        "days_left": days_left,
        "created": created,
        "status": status
    }

def get_proxy_age(user_id: int, proxy_name: str) -> dict:
    """Получить возраст прокси"""
    user_proxies = load_json(USER_PROXIES_FILE, {})
    user_id_str = str(user_id)
    
    if user_id_str not in user_proxies or "proxies" not in user_proxies[user_id_str]:
        return {"days": 0, "status": "not_found"}
    
    for proxy in user_proxies[user_id_str]["proxies"]:
        if proxy.get("name") == proxy_name and "issued_at" in proxy:
            issued_at = datetime.fromisoformat(proxy["issued_at"])
            days_since = (datetime.now() - issued_at).days
            days_left = PROXY_EXPIRY_DAYS - days_since
            
            if days_left < 0:
                status = "expired"
            elif days_left <= 7:
                status = "expiring_soon"
            else:
                status = "active"
            
            return {
                "days": days_since,
                "days_left": days_left,
                "issued_at": issued_at,
                "status": status
            }
    
    return {"days": 0, "status": "not_found"}

def format_expiry_indicator(days_left: int, status: str) -> str:
    """Форматировать индикатор срока"""
    if status == "expired":
        return f"❌ <b>ИСТЁК {abs(days_left)} дн. назад</b>"
    elif status == "expiring_soon":
        return f"⚠️ <b>Истекает через {days_left} дн.</b>"
    else:
        return f"✅ Активен (осталось {days_left} дн.)"

def check_all_vpn_expiry() -> list:
    """Проверить все VPN конфиги на истечение"""
    expired = []
    expiring_soon = []
    
    if not os.path.exists(VPN_DIR):
        return expired, expiring_soon
    
    for username in os.listdir(VPN_DIR):
        user_dir = os.path.join(VPN_DIR, username)
        if not os.path.isdir(user_dir):
            continue
        
        for filename in os.listdir(user_dir):
            if filename.endswith('.vpn'):
                age = get_vpn_config_age(username, filename)
                if age["status"] == "expired":
                    expired.append({
                        "username": username,
                        "filename": filename,
                        "days_expired": abs(age["days_left"])
                    })
                elif age["status"] == "expiring_soon":
                    expiring_soon.append({
                        "username": username,
                        "filename": filename,
                        "days_left": age["days_left"]
                    })
    
    return expired, expiring_soon

def check_all_proxy_expiry() -> list:
    """Проверить все прокси на истечение"""
    user_proxies = load_json(USER_PROXIES_FILE, {})
    expired = []
    expiring_soon = []
    
    for user_id_str, data in user_proxies.items():
        if "proxies" not in data:
            continue
        
        for proxy in data["proxies"]:
            if "issued_at" not in proxy:
                continue
            
            issued_at = datetime.fromisoformat(proxy["issued_at"])
            days_since = (datetime.now() - issued_at).days
            days_left = PROXY_EXPIRY_DAYS - days_since
            
            if days_left < 0:
                expired.append({
                    "user_id": user_id_str,
                    "proxy_name": proxy.get("name", "Без названия"),
                    "days_expired": abs(days_left)
                })
            elif days_left <= 7:
                expiring_soon.append({
                    "user_id": user_id_str,
                    "proxy_name": proxy.get("name", "Без названия"),
                    "days_left": days_left
                })
    
    return expired, expiring_soon
