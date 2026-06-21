from aiogram import Router, F, types
from config import ADMIN_IDS
from repositories.vpn_repository import load_vpn_db
from database.storage import load_json
from keyboards.inline import get_back_keyboard
from utils.expiry import is_proxy_expired
router = Router()
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

