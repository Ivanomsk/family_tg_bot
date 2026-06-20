import os
import json
import logging
from datetime import datetime, timedelta
from config import ALLOWED_CHAT_ID, VPN_DIR, VPN_EXPIRY_DAYS, USER_PROXIES_FILE, PROXY_EXPIRY_DAYS
from database.storage import load_json, save_json
from utils.vpn_manager import VPN_USERS_FILE, load_vpn_db
from utils.expiry import get_proxy_expiry_date, is_proxy_expired
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)

NOTIFICATIONS_FILE = os.path.join("bot_data", "last_notifications.json")
PERSONAL_NOTIFICATIONS_FILE = os.path.join("bot_data", "personal_notifications.json")


# ============================================
# ОБЩИЕ ФУНКЦИИ
# ============================================

def get_notification_cooldown() -> dict:
    return load_json(NOTIFICATIONS_FILE, {})


def save_notification_cooldown(data: dict):
    save_json(NOTIFICATIONS_FILE, data)


def can_notify(user_id: int, notification_type: str, cooldown_hours: int = 24) -> bool:
    cooldown = get_notification_cooldown()
    key = f"{user_id}_{notification_type}"
    if key not in cooldown:
        return True
    last_notify = datetime.fromisoformat(cooldown[key])
    hours_since = (datetime.now() - last_notify).total_seconds() / 3600
    return hours_since >= cooldown_hours


def mark_notified(user_id: int, notification_type: str):
    cooldown = get_notification_cooldown()
    key = f"{user_id}_{notification_type}"
    cooldown[key] = datetime.now().isoformat()
    save_notification_cooldown(cooldown)


def format_user_mention(user_id: int, username: str) -> str:
    if username:
        return f"@{username}"
    return f"<a href='tg://user?id={user_id}'>Пользователь</a>"


# ============================================
# УВЕДОМЛЕНИЯ В ЧАТ
# ============================================

async def send_vpn_expiry_notification(bot, user_id: int, username: str, expired_configs: list, expiring_configs: list):
    if not expired_configs and not expiring_configs:
        return
    if expired_configs and not can_notify(user_id, 'vpn_expired'):
        return
    if expiring_configs and not can_notify(user_id, 'vpn_expiring'):
        return
    
    mention = format_user_mention(user_id, username)
    text = f"🔔 <b>Уведомление о VPN</b>\n\n{mention}, внимание!\n\n"
    
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
        if expired_configs:
            mark_notified(user_id, 'vpn_expired')
        if expiring_configs:
            mark_notified(user_id, 'vpn_expiring')
        logger.info(f"📢 Отправлено уведомление о VPN для @{username} в чат")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о VPN: {e}")


async def send_proxy_expiry_notification(bot, user_id: int, username: str, expired_proxies: list, expiring_proxies: list):
    if not expired_proxies and not expiring_proxies:
        return
    if expired_proxies and not can_notify(user_id, 'proxy_expired'):
        return
    if expiring_proxies and not can_notify(user_id, 'proxy_expiring'):
        return
    
    mention = format_user_mention(user_id, username)
    text = f"🔔 <b>Уведомление о прокси</b>\n\n{mention}, внимание!\n\n"
    
    if expired_proxies:
        text += f"❌ <b>Истекли прокси ({len(expired_proxies)}):</b>\n"
        for proxy in expired_proxies[:3]:
            text += f"  • {proxy['proxy_name']}\n"
        if len(expired_proxies) > 3:
            text += f"  • ... и ещё {len(expired_proxies) - 3}\n"
        text += "\n"
    
    if expiring_proxies:
        text += f"⚠️ <b>Скоро истекут ({len(expiring_proxies)}):</b>\n"
        for proxy in expiring_proxies[:3]:
            text += f"  • {proxy['proxy_name']} (осталось {proxy['days_left']} дн.)\n"
        text += "\n"
    
    text += "💡 Используй /request_proxy чтобы запросить новые прокси"
    
    try:
        await bot.send_message(ALLOWED_CHAT_ID, text, parse_mode="HTML")
        if expired_proxies:
            mark_notified(user_id, 'proxy_expired')
        if expiring_proxies:
            mark_notified(user_id, 'proxy_expiring')
        logger.info(f"📢 Отправлено уведомление о прокси для @{username} в чат")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о прокси: {e}")


# ============================================
# ЛИЧНЫЕ УВЕДОМЛЕНИЯ (VPN)
# ============================================

def load_personal_notifications() -> dict:
    return load_json(PERSONAL_NOTIFICATIONS_FILE, {})


def save_personal_notifications(data: dict):
    save_json(PERSONAL_NOTIFICATIONS_FILE, data)


def can_send_personal_notification(user_id: int, config_hash: str, days: int) -> bool:
    data = load_personal_notifications()
    key = f"{user_id}_{config_hash}_{days}"
    if key not in data:
        return True
    last_sent = datetime.fromisoformat(data[key])
    hours_since = (datetime.now() - last_sent).total_seconds() / 3600
    return hours_since >= 24


def mark_personal_notification_sent(user_id: int, config_hash: str, days: int):
    data = load_personal_notifications()
    key = f"{user_id}_{config_hash}_{days}"
    data[key] = datetime.now().isoformat()
    save_personal_notifications(data)


async def send_personal_expiry_notification(bot, user_id: int, username: str, config_hash: str, expires_at: str, days_left: int):
    if not can_send_personal_notification(user_id, config_hash, days_left):
        return False
    
    emoji = "🔴" if days_left == 1 else "🟡" if days_left == 3 else "🟢"
    text = (
        f"{emoji} <b>ВНИМАНИЕ!</b>\n\n"
        f"Ваш VPN-конфиг <b>«{username}»</b> истекает "
        f"<b>через {days_left} дня(ей)</b>!\n\n"
        f"📅 Дата истечения: <code>{expires_at}</code>\n\n"
        f"Нажмите кнопку для продления на 30 дней:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Продлить на 30 дней", callback_data=f"extend_vpn_{user_id}_{config_hash}")],
        [InlineKeyboardButton(text="📋 Мои конфиги", callback_data="show_my_configs")]
    ])
    
    try:
        await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=keyboard)
        mark_personal_notification_sent(user_id, config_hash, days_left)
        logger.info(f"📨 Личное уведомление отправлено пользователю {user_id} ({username}, {days_left} дней)")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки личного уведомления {user_id}: {e}")
        return False


async def check_and_send_personal_notifications(bot):
    vpn_users = load_vpn_db()
    if not vpn_users:
        return 0
    
    now = datetime.now()
    check_days = [7, 3, 1]
    sent_count = 0
    
    for config_hash, config_data in vpn_users.items():
        if config_data.get('permanent', False):
            continue
        
        user_id = config_data.get('user_id')
        username = config_data.get('username')
        expires_at_str = config_data.get('expires_at')
        
        if not user_id or not expires_at_str:
            continue
        if not config_data.get('active', True):
            continue
        
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
        except ValueError:
            continue
        
        days_left = (expires_at - now).days
        
        for days in check_days:
            if days_left == days:
                sent = await send_personal_expiry_notification(
                    bot, user_id, username, config_hash, expires_at_str, days
                )
                if sent:
                    sent_count += 1
    
    return sent_count


# ============================================
# ЛИЧНЫЕ УВЕДОМЛЕНИЯ ДЛЯ ПРОКСИ
# ============================================

async def send_proxy_personal_notification(bot, user_id: int, username: str, proxy_name: str, days_left: int):
    emoji = "🔴" if days_left == 1 else "🟡" if days_left == 3 else "🟢"
    
    text = (
        f"{emoji} <b>ВНИМАНИЕ!</b>\n\n"
        f"Ваш прокси <b>«{proxy_name}»</b> истекает "
        f"<b>через {days_left} дня(ей)</b>!\n\n"
        f"Нажмите кнопку для продления на 30 дней:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Запросить продление", callback_data=f"proxy_extend_{user_id}_{0}")],
        [InlineKeyboardButton(text="📋 Мои прокси", callback_data="menu_proxy")]
    ])
    
    try:
        await bot.send_message(user_id, text, parse_mode="HTML", reply_markup=keyboard)
        logger.info(f"📨 Уведомление о прокси отправлено пользователю {user_id} ({proxy_name}, {days_left} дней)")
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления о прокси {user_id}: {e}")
        return False


async def check_proxy_notifications(bot):
    user_proxies = load_json(USER_PROXIES_FILE, {})
    if not user_proxies:
        return 0
    
    now = datetime.now()
    check_days = [7, 3, 1]
    sent_count = 0
    
    for user_id_str, data in user_proxies.items():
        user_id = int(user_id_str)
        proxies = data.get("proxies", [])
        
        username = None
        try:
            stats = load_json("bot_data/stats.json", {})
            if str(user_id) in stats:
                username = stats[str(user_id)].get('username')
        except:
            pass
        
        for proxy in proxies:
            if proxy.get('permanent', False):
                continue
            
            issued_at = proxy.get('issued_at')
            if not issued_at:
                continue
            
            try:
                issued_date = datetime.fromisoformat(issued_at)
                expires_date = issued_date + timedelta(days=PROXY_EXPIRY_DAYS)
                days_left = (expires_date - now).days
                
                if days_left in check_days:
                    sent = await send_proxy_personal_notification(
                        bot, user_id, username or f"ID:{user_id}", proxy['name'], days_left
                    )
                    if sent:
                        sent_count += 1
            except Exception as e:
                logger.error(f"Ошибка проверки прокси {proxy.get('name')}: {e}")
    
    return sent_count
