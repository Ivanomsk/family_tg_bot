from aiogram import Router, F, types
from config import ADMIN_IDS

router = Router()

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
