from aiogram import Router, F, types
from config import ADMIN_IDS
from repositories.vpn_repository import load_vpn_db
from database.storage import load_json
from keyboards.inline import get_back_keyboard
from datetime import datetime
router = Router()
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


