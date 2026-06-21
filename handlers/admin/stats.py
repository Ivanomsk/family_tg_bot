from aiogram import Router, types, F
from config import ADMIN_IDS, USER_PROXIES_FILE
from utils.logger import standard_logger
from database.storage import load_json
from repositories.vpn_repository import load_vpn_db
from services.traffic_service import (
    format_size,
    get_user_traffic_from_clients_table,
)
from keyboards.inline import get_back_keyboard

router = Router()
logger = standard_logger


@router.callback_query(F.data == "menu_stats")
async def menu_stats(callback: types.CallbackQuery):
    """Статистика использования (админ)"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    stats = load_json("bot_data/stats.json", {})
    user_proxies = load_json(USER_PROXIES_FILE, {})
    traffic_data = get_user_traffic_from_clients_table()
    
    if not stats and not traffic_data:
        await callback.message.edit_text(
            "📊 Статистики пока нет.",
            reply_markup=get_back_keyboard("menu_admin_main").as_markup(),
            parse_mode="HTML"
        )
        return
    
    # Собираем данные по пользователям
    users_info = {}
    vpn_users = load_vpn_db()
    
    for key, data in vpn_users.items():
        username = data.get('username', 'unknown')
        if username not in users_info:
            users_info[username] = {
                'user_id': data.get('user_id'),
                'vpn_configs': 0,
                'proxies': 0,
                'traffic': '0 B',
                'traffic_bytes': 0,
                'last_handshake': 'никогда',
                'ip': '',
                'actions': 0,
                'vpn_requests': 0
            }
        if data.get('active', True):
            users_info[username]['vpn_configs'] += 1
    
    for user_id_str, data in user_proxies.items():
        user_id = int(user_id_str)
        proxies = data.get('proxies', [])
        username = None
        for key, vpn_data in vpn_users.items():
            if vpn_data.get('user_id') == user_id:
                username = vpn_data.get('username')
                break
        if not username:
            for uid, sdata in stats.items():
                if int(uid) == user_id:
                    username = sdata.get('username')
                    break
        if username:
            if username not in users_info:
                users_info[username] = {
                    'user_id': user_id,
                    'vpn_configs': 0,
                    'proxies': 0,
                    'traffic': '0 B',
                    'traffic_bytes': 0,
                    'last_handshake': 'никогда',
                    'ip': '',
                    'actions': 0,
                    'vpn_requests': 0
                }
            users_info[username]['proxies'] = len(proxies)
    
    for user_id_str, data in stats.items():
        username = data.get('username')
        if username and username in users_info:
            users_info[username]['actions'] = sum(data.get('actions', {}).values())
            users_info[username]['vpn_requests'] = data.get('actions', {}).get('vpn', 0)
    
    for username, traffic in traffic_data.items():
        if username in users_info:
            users_info[username]['traffic'] = traffic.get('total', '0 B')
            users_info[username]['traffic_bytes'] = traffic.get('total_bytes', 0)
            users_info[username]['last_handshake'] = traffic.get('last_handshake', 'никогда')
            users_info[username]['ip'] = traffic.get('ip', '')
        else:
            users_info[username] = {
                'user_id': None,
                'vpn_configs': 0,
                'proxies': 0,
                'traffic': traffic.get('total', '0 B'),
                'traffic_bytes': traffic.get('total_bytes', 0),
                'last_handshake': traffic.get('last_handshake', 'никогда'),
                'ip': traffic.get('ip', ''),
                'actions': 0,
                'vpn_requests': 0
            }
    
    if not users_info:
        await callback.message.edit_text(
            "📊 Нет данных.",
            reply_markup=get_back_keyboard("menu_admin_main").as_markup(),
            parse_mode="HTML"
        )
        return
    
    text = "📊 <b>СТАТИСТИКА ИСПОЛЬЗОВАНИЯ</b>\n\n"
    sorted_users = sorted(
        users_info.items(),
        key=lambda x: (x[1]['traffic_bytes'], x[1]['vpn_configs']),
        reverse=True
    )
    
    for username, data in sorted_users:
        vpn_configs = data.get('vpn_configs', 0)
        proxies = data.get('proxies', 0)
        traffic = data.get('traffic', '0 B')
        last_handshake = data.get('last_handshake', 'никогда')
        ip = data.get('ip', '')
        actions = data.get('actions', 0)
        vpn_requests = data.get('vpn_requests', 0)
        
        if last_handshake != 'никогда':
            status = "🟢"
        elif vpn_configs > 0:
            status = "🟡"
        else:
            status = "⚪"
        
        display_name = f"@{username}" if username != 'unknown' else username
        text += f"{status} <b>{display_name}</b>\n"
        text += f"   📥 Трафик: {traffic}\n"
        text += f"   🗂️ Конфигов: {vpn_configs} | 🛰 Прокси: {proxies}\n"
        if actions > 0:
            text += f"   📊 Действий: {actions} (VPN запросов: {vpn_requests})\n"
        if last_handshake != 'никогда':
            text += f"   🕐 Последнее подключение: {last_handshake}\n"
        if ip:
            text += f"   🌐 IP: {ip}\n"
        text += "\n"
    
    total_traffic_bytes = sum(u.get('traffic_bytes', 0) for u in users_info.values())
    total_traffic = format_size(total_traffic_bytes) if total_traffic_bytes > 0 else "0 B"
    total_users = len(users_info)
    total_configs = sum(u.get('vpn_configs', 0) for u in users_info.values())
    total_proxies = sum(u.get('proxies', 0) for u in users_info.values())
    
    text += f"━━━━━━━━━━━━━━━━━━━━\n"
    text += f"📌 <b>Всего пользователей:</b> {total_users}\n"
    text += f"📌 <b>Всего конфигов:</b> {total_configs}\n"
    text += f"📌 <b>Всего прокси:</b> {total_proxies}\n"
    text += f"📌 <b>Общий трафик:</b> {total_traffic}\n"
    text += f"\n🟢 — активен | 🟡 — есть конфиг | ⚪ — неактивен"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_admin_main").as_markup()
    )


@router.callback_query(F.data == "admin_check_expiry")
async def admin_check_expiry(callback: types.CallbackQuery):
    """Проверка сроков — детальная информация"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    await callback.answer()
    
    from utils.expiry import check_all_vpn_expiry, check_all_proxy_expiry
    
    vpn_expired, vpn_expiring = check_all_vpn_expiry()
    proxy_expired, proxy_expiring = check_all_proxy_expiry()
    
    vpn_users = load_vpn_db()
    permanent_count = 0
    for ch, cd in vpn_users.items():
        if cd.get('permanent', False) and cd.get('active', True):
            permanent_count += 1
    
    text = "🔍 <b>ПРОВЕРКА СРОКОВ</b>\n\n"
    text += "🔐 <b>VPN конфиги:</b>\n"
    if permanent_count > 0:
        text += f"   ♾️ Бессрочных: {permanent_count}\n"
    
    if vpn_expired:
        text += f"   ❌ <b>Истекли ({len(vpn_expired)}):</b>\n"
        for item in vpn_expired:
            text += f"      • @{item['username']} — {item['filename']}\n"
    else:
        text += "   ✅ Истекших нет\n"
    
    if vpn_expiring:
        text += f"   ⚠️ <b>Истекают ({len(vpn_expiring)}):</b>\n"
        for item in vpn_expiring:
            days = item['days_left']
            emoji = "🔴" if days <= 1 else "🟡" if days <= 3 else "🟢"
            text += f"      • {emoji} @{item['username']} — {item['filename']} ({days} дн.)\n"
    else:
        text += "   ✅ Истекающих нет\n"
    
    text += "\n🛰 <b>Прокси:</b>\n"
    if proxy_expired:
        text += f"   ❌ <b>Истекли ({len(proxy_expired)}):</b>\n"
        for item in proxy_expired:
            text += f"      • ID {item['user_id']} — {item['proxy_name']}\n"
    else:
        text += "   ✅ Истекших нет\n"
    
    if proxy_expiring:
        text += f"   ⚠️ <b>Истекают ({len(proxy_expiring)}):</b>\n"
        for item in proxy_expiring:
            days = item['days_left']
            emoji = "🔴" if days <= 1 else "🟡" if days <= 3 else "🟢"
            text += f"      • {emoji} ID {item['user_id']} — {item['proxy_name']} ({days} дн.)\n"
    else:
        text += "   ✅ Истекающих нет\n"
    
    total_expired = len(vpn_expired) + len(proxy_expired)
    total_expiring = len(vpn_expiring) + len(proxy_expiring)
    
    if total_expired == 0 and total_expiring == 0 and permanent_count == 0:
        text += "\n━━━━━━━━━━━━━━━━━━━━\n"
        text += "✅ <b>Все конфиги и прокси активны!</b>"
    else:
        text += "\n━━━━━━━━━━━━━━━━━━━━\n"
        if total_expired > 0:
            text += f"❌ <b>Истекло:</b> {total_expired}\n"
        if total_expiring > 0:
            text += f"⚠️ <b>Истекает:</b> {total_expiring}\n"
        if permanent_count > 0:
            text += f"♾️ <b>Бессрочных:</b> {permanent_count}\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_admin_main").as_markup()
    )
