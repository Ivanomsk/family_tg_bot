from aiogram import Router, types, F
from config import ADMIN_IDS
from utils.logger import standard_logger
from database.storage import load_json
from utils.vpn_manager import load_vpn_db
from keyboards.inline import get_back_keyboard
from datetime import datetime

router = Router()
logger = standard_logger


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    """Управление пользователями"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    from keyboards.inline import get_admin_users_keyboard
    await callback.message.edit_text(
        "👥 <b>Управление пользователями</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_users_keyboard().as_markup()
    )


@router.callback_query(F.data == "admin_vpn_list")
async def admin_vpn_list(callback: types.CallbackQuery):
    """Список VPN пользователей"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    vpn_users = load_vpn_db()
    if not vpn_users:
        await callback.message.edit_text(
            "📭 Нет активных VPN конфигов.",
            reply_markup=get_back_keyboard("admin_users").as_markup(),
            parse_mode="HTML"
        )
        return
    
    users = {}
    for public_key, data in vpn_users.items():
        username = data.get('username', 'unknown')
        user_id_data = data.get('user_id')
        active = data.get('active', True)
        permanent = data.get('permanent', False)
        expires_at = data.get('expires_at', 'не указана')
        
        if expires_at != 'не указана':
            try:
                dt = datetime.fromisoformat(expires_at)
                expires_display = dt.strftime('%d.%m.%Y %H:%M')
            except:
                expires_display = expires_at
        else:
            expires_display = 'не указана'
        
        if username not in users:
            users[username] = {
                'user_id': user_id_data,
                'configs': [],
                'total': 0
            }
        users[username]['configs'].append({
            'active': active,
            'permanent': permanent,
            'expires_at': expires_display
        })
        users[username]['total'] += 1
    
    text = "📋 <b>СПИСОК VPN ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
    for username, data in sorted(users.items()):
        user_id_data = data['user_id']
        username_display = f"@{username}" if username != 'unknown' else f"ID:{user_id_data}"
        text += f"👤 {username_display} (ID: {user_id_data})\n"
        text += f"   📁 Конфигов: {data['total']}\n"
        for conf in data['configs']:
            if conf['permanent']:
                status = "♾️ Бессрочный"
            elif conf['active']:
                status = "✅ Активен"
            else:
                status = "❌ Неактивен"
            text += f"      {status} | истекает: {conf['expires_at']}\n"
        text += "\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_users").as_markup()
    )


@router.callback_query(F.data == "admin_vpn_revoke")
async def admin_vpn_revoke_menu(callback: types.CallbackQuery):
    """Меню отзыва VPN"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    text = (
        "🗑️ <b>ОТОЗВАТЬ VPN</b>\n\n"
        "Используйте команду:\n"
        "<code>/revoke username</code> — отозвать ВСЕ конфиги пользователя\n"
        "<code>/revoke username public_key</code> — отозвать конкретный\n\n"
        "📝 <b>Примеры:</b>\n"
        "<code>/revoke Ivan_Mos</code>\n"
        "<code>/revoke Ivan_Mos pXsM/uIIRo0xv0AMTnVF</code>\n\n"
        "💡 <i>Конфиг будет удалён с сервера и помечен как неактивный</i>"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_users").as_markup()
    )


@router.callback_query(F.data == "admin_proxy_list")
async def admin_proxy_list(callback: types.CallbackQuery):
    """Список прокси"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    user_proxies = load_json("bot_data/user_proxies.json", {})
    if not user_proxies:
        await callback.message.edit_text(
            "📭 Нет пользователей с прокси.",
            reply_markup=get_back_keyboard("admin_users").as_markup(),
            parse_mode="HTML"
        )
        return
    
    stats = load_json("bot_data/stats.json", {})
    text = "🛰 <b>Список прокси пользователей</b>\n\n"
    
    for user_id_str, data in user_proxies.items():
        user_id = int(user_id_str)
        proxies = data.get("proxies", [])
        if proxies:
            username = stats.get(user_id_str, {}).get('username')
            if username:
                display_name = f"@{username} (ID: {user_id_str})"
            else:
                display_name = f"ID: {user_id_str}"
            text += f"👤 {display_name} ({len(proxies)}):\n"
            for p in proxies:
                is_permanent = p.get('permanent', False)
                status = "♾️" if is_permanent else "📅"
                text += f"  {status} {p.get('name')} | {p.get('server')}:{p.get('port')}\n"
            text += "\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_users").as_markup()
    )


@router.callback_query(F.data == "admin_permanent_menu")
async def admin_permanent_menu(callback: types.CallbackQuery):
    """Бессрочный VPN"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    vpn_users = load_vpn_db()
    if not vpn_users:
        await callback.message.edit_text(
            "📭 Нет пользователей с конфигами.",
            reply_markup=get_back_keyboard("menu_admin_main").as_markup(),
            parse_mode="HTML"
        )
        return
    
    users = {}
    for ch, cd in vpn_users.items():
        username = cd.get('username', 'unknown')
        if username not in users:
            users[username] = []
        users[username].append({
            'hash': ch,
            'permanent': cd.get('permanent', False),
            'active': cd.get('active', True)
        })
    
    text = (
        "♾️ <b>Управление бессрочным статусом VPN</b>\n\n"
        "💡 <b>Используйте команду:</b>\n"
        "<code>/permanent username filename on/off</code>\n\n"
        "📝 <b>Примеры:</b>\n"
        "<code>/permanent Ivan_Mos Для_пк_Исиль.vpn on</code>\n"
        "<code>/permanent Ivan_Mos Для_пк_Исиль.vpn off</code>\n\n"
        "📋 <b>Список пользователей:</b>\n"
    )
    
    for username, configs in users.items():
        active_count = sum(1 for c in configs if c['active'])
        username_display = f"@{username}" if username else "unknown"
        text += f"\n👤 {username_display} ({active_count} конфигов)"
        for c in configs:
            status = "♾️" if c['permanent'] else "📅"
            active = "✅" if c['active'] else "❌"
            text += f"\n  {status} {active} {c['hash'][:20]}..."
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_admin_main").as_markup()
    )


@router.callback_query(F.data == "admin_permanent_proxy_menu")
async def admin_permanent_proxy_menu(callback: types.CallbackQuery):
    """Бессрочный прокси"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    user_proxies = load_json("bot_data/user_proxies.json", {})
    if not user_proxies:
        await callback.message.edit_text(
            "📭 Нет пользователей с прокси.",
            reply_markup=get_back_keyboard("menu_admin_main").as_markup(),
            parse_mode="HTML"
        )
        return
    
    stats = load_json("bot_data/stats.json", {})
    text = (
        "♾️ <b>Управление бессрочным статусом прокси</b>\n\n"
        "💡 <b>Используйте команду:</b>\n"
        "<code>/permanent_proxy user_id имя_прокси on/off</code>\n\n"
        "📝 <b>Примеры:</b>\n"
        "<code>/permanent_proxy 764438696 Основной on</code>\n"
        "<code>/permanent_proxy 764438696 Основной off</code>\n\n"
        "📋 <b>Список пользователей с прокси:</b>\n"
    )
    
    from utils.expiry import is_proxy_expired
    
    for user_id_str, data in user_proxies.items():
        user_id = int(user_id_str)
        proxies = data.get("proxies", [])
        active_proxies = [p for p in proxies if not is_proxy_expired(user_id, p.get('name'))]
        if active_proxies:
            username = stats.get(user_id_str, {}).get('username')
            if username:
                display_name = f"@{username} (ID: {user_id_str})"
            else:
                display_name = f"ID: {user_id_str}"
            text += f"\n👤 {display_name} ({len(active_proxies)} прокси)"
            for p in active_proxies:
                status = "♾️" if p.get('permanent', False) else "📅"
                text += f"\n  {status} {p.get('name')}"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_admin_main").as_markup()
    )

@router.callback_query(F.data == "admin_user_manage")
async def admin_user_manage(callback: types.CallbackQuery):
    """Управление пользователем (меню)"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    # Получаем список пользователей
    vpn_users = load_vpn_db()
    stats = load_json("bot_data/stats.json", {})
    
    if not vpn_users and not stats:
        await callback.message.edit_text(
            "📭 Нет пользователей.",
            reply_markup=get_back_keyboard("admin_users").as_markup(),
            parse_mode="HTML"
        )
        return
    
    # Собираем уникальных пользователей
    users = set()
    for data in vpn_users.values():
        username = data.get('username')
        if username:
            users.add(username)
    for data in stats.values():
        username = data.get('username')
        if username:
            users.add(username)
    
    text = "👤 <b>УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЕМ</b>\n\n"
    text += "📋 <b>Список пользователей:</b>\n"
    
    for username in sorted(users):
        config_count = sum(1 for d in vpn_users.values() if d.get('username') == username and d.get('active', True))
        text += f"   • @{username} (конфигов: {config_count})\n"
    
    text += "\n━━━━━━━━━━━━━━━━━━━━\n"
    text += "💡 <b>Используйте команды:</b>\n\n"
    text += "<code>/userinfo @username</code> — информация о пользователе\n"
    text += "<code>/deluser @username</code> — удалить пользователя полностью\n"
    text += "<code>/revoke @username</code> — отозвать конфиги\n"
    text += "<code>/clearuser username</code> — удалить файлы конфигов\n\n"
    text += "📝 <b>Примеры:</b>\n"
    text += "<code>/userinfo @Ivan_Mos</code>\n"
    text += "<code>/deluser @Ivan_Mos</code>"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_users").as_markup()
    )