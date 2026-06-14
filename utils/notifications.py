import os
import json
import logging
from datetime import datetime
from config import ALLOWED_CHAT_ID, VPN_DIR, VPN_EXPIRY_DAYS, USER_PROXIES_FILE, PROXY_EXPIRY_DAYS
from database.storage import load_json, save_json

logger = logging.getLogger(__name__)

# Файл для хранения времени последних уведомлений
NOTIFICATIONS_FILE = os.path.join("bot_data", "last_notifications.json")

def get_notification_cooldown() -> dict:
    """Получить данные о последних уведомлениях"""
    return load_json(NOTIFICATIONS_FILE, {})

def save_notification_cooldown(data: dict):
    """Сохранить данные о последних уведомлениях"""
    save_json(NOTIFICATIONS_FILE, data)

def can_notify(user_id: int, notification_type: str, cooldown_hours: int = 24) -> bool:
    # Измените 24 на другое значение:
    # 12 — раз в 12 часов
    # 48 — раз в 2 дня
    # 168 — раз в неделю
    """
    Проверить, можно ли отправить уведомление (чтобы не спамить)
    notification_type: 'vpn_expired', 'vpn_expiring', 'proxy_expired', 'proxy_expiring'
    """
    cooldown = get_notification_cooldown()
    key = f"{user_id}_{notification_type}"
    
    if key not in cooldown:
        return True
    
    last_notify = datetime.fromisoformat(cooldown[key])
    hours_since = (datetime.now() - last_notify).total_seconds() / 3600
    
    return hours_since >= cooldown_hours

def mark_notified(user_id: int, notification_type: str):
    """Отметить что уведомление отправлено"""
    cooldown = get_notification_cooldown()
    key = f"{user_id}_{notification_type}"
    cooldown[key] = datetime.now().isoformat()
    save_notification_cooldown(cooldown)

def format_user_mention(user_id: int, username: str) -> str:
    """Форматировать упоминание пользователя"""
    if username:
        return f"@{username}"
    return f"<a href='tg://user?id={user_id}'>Пользователь</a>"

async def send_vpn_expiry_notification(bot, user_id: int, username: str, expired_configs: list, expiring_configs: list):
    """Отправить уведомление об истечении VPN в чат"""
    if not expired_configs and not expiring_configs:
        return
    
    # Проверяем cooldown
    if expired_configs and not can_notify(user_id, 'vpn_expired'):
        return
    if expiring_configs and not can_notify(user_id, 'vpn_expiring'):
        return
    
    mention = format_user_mention(user_id, username)
    
    text = f"🔔 <b>Уведомление о VPN</b>\n\n"
    text += f"{mention}, внимание!\n\n"
    
    if expired_configs:
        text += f"❌ <b>Истекли VPN конфиги ({len(expired_configs)}):</b>\n"
        for conf in expired_configs[:3]:
            text += f"  • {conf['filename']}\n"
        if len(expired_configs) > 3:
            text += f"  • ... и ещё {len(expired_configs) - 3}\n"
        text += "\n"
    
    if expiring_configs:
        text += f"⚠️ <b>Скоро истекут ({len(expiring_configs)}):</b>\n"
        for conf in expiring_configs[:3]:
            text += f"  • {conf['filename']} (осталось {conf['days_left']} дн.)\n"
        text += "\n"
    
    text += "💡 Используй /vpn чтобы запросить новые конфиги"
    
    try:
        await bot.send_message(ALLOWED_CHAT_ID, text, parse_mode="HTML")
        
        # Отмечаем что уведомление отправлено
        if expired_configs:
            mark_notified(user_id, 'vpn_expired')
        if expiring_configs:
            mark_notified(user_id, 'vpn_expiring')
        
        logger.info(f" Отправлено уведомление о VPN для @{username} в чат")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о VPN: {e}")

async def send_proxy_expiry_notification(bot, user_id: int, username: str, expired_proxies: list, expiring_proxies: list):
    """Отправить уведомление об истечении прокси в чат"""
    if not expired_proxies and not expiring_proxies:
        return
    
    # Проверяем cooldown
    if expired_proxies and not can_notify(user_id, 'proxy_expired'):
        return
    if expiring_proxies and not can_notify(user_id, 'proxy_expiring'):
        return
    
    mention = format_user_mention(user_id, username)
    
    text = f"🔔 <b>Уведомление о прокси</b>\n\n"
    text += f"{mention}, внимание!\n\n"
    
    if expired_proxies:
        text += f"❌ <b>Истекли прокси ({len(expired_proxies)}):</b>\n"
        for proxy in expired_proxies[:3]:
            text += f"  • {proxy['name']}\n"
        if len(expired_proxies) > 3:
            text += f"  • ... и ещё {len(expired_proxies) - 3}\n"
        text += "\n"
    
    if expiring_proxies:
        text += f"️ <b>Скоро истекут ({len(expiring_proxies)}):</b>\n"
        for proxy in expiring_proxies[:3]:
            text += f"  • {proxy['name']} (осталось {proxy['days_left']} дн.)\n"
        text += "\n"
    
    text += "💡 Используй /request_proxy чтобы запросить новые прокси"
    
    try:
        await bot.send_message(ALLOWED_CHAT_ID, text, parse_mode="HTML")
        
        # Отмечаем что уведомление отправлено
        if expired_proxies:
            mark_notified(user_id, 'proxy_expired')
        if expiring_proxies:
            mark_notified(user_id, 'proxy_expiring')
        
        logger.info(f" Отправлено уведомление о прокси для @{username} в чат")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о прокси: {e}")
