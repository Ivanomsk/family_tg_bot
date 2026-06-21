from aiogram import Router, F, types
from datetime import datetime, timedelta

from config import USER_PROXIES_FILE
from database.storage import load_json
from keyboards.inline import get_back_keyboard
from handlers.main_menu import require_private_chat

router = Router()

# ==========================================
# ВЫБОР ПРОКСИ (КАРТОЧКА)
# ==========================================

@router.callback_query(F.data.startswith("proxy_select_"))
async def proxy_select(callback: types.CallbackQuery):
    if not await require_private_chat(callback, "просмотр прокси"):
        return
    
    await callback.answer()
    
    user_id = callback.from_user.id
    user_proxies = load_json(USER_PROXIES_FILE, {})
    proxies = user_proxies.get(str(user_id), {}).get("proxies", [])
    
    try:
        index = int(callback.data.split("_")[-1])
        proxy = proxies[index]
    except (IndexError, ValueError):
        await callback.answer("❌ Прокси не найден", show_alert=True)
        return
    
    username = callback.from_user.username or f"ID:{user_id}"
    tg_link = f"tg://proxy?server={proxy['server']}&port={proxy['port']}&secret={proxy['secret']}"
    
    issued_at_raw = proxy.get('issued_at', 'не указана')
    if issued_at_raw != 'не указана':
        try:
            issued_dt = datetime.fromisoformat(issued_at_raw)
            issued_at = issued_dt.strftime('%d.%m.%Y %H:%M')
        except:
            issued_at = issued_at_raw
    else:
        issued_at = 'не указана'
    
    is_permanent = proxy.get('permanent', False)
    
    expires_at = None
    days_left = None
    is_expired = False
    
    if not is_permanent and issued_at_raw != 'не указана':
        try:
            issued_date = datetime.fromisoformat(issued_at_raw)
            expires_date = issued_date + timedelta(days=30)
            expires_at = expires_date.strftime('%d.%m.%Y')
            days_left = (expires_date - datetime.now()).days
            if days_left < 0:
                is_expired = True
        except:
            pass
    
    if is_permanent:
        status = "♾️ Бессрочный"
    elif is_expired:
        status = "🔴 Истек"
    elif days_left is not None and days_left <= 3:
        status = f"🟡 Истекает через {days_left} дн."
    else:
        status = "🟢 Активен"
    
    text = (
        f"🔒 <b>Карточка прокси</b>\n\n"
        f"👤 <b>Пользователь:</b> @{username}\n"
        f"📁 <b>Имя:</b> {proxy['name']}\n"
        f"🌐 <b>Сервер:</b> {proxy['server']}\n"
        f"🔌 <b>Порт:</b> {proxy['port']}\n"
        f"📅 <b>Выдан:</b> {issued_at}\n"
        f"📅 <b>Истекает:</b> {expires_at if expires_at else ('♾️ Бессрочный' if is_permanent else 'не указана')}\n"
        f"📊 <b>Статус:</b> {status}\n"
    )
    
    buttons = []
    
    if not is_expired or is_permanent:
        buttons.append([InlineKeyboardButton(
            text="📱 Подключить в Telegram",
            url=tg_link
        )])
    
    if not is_permanent:
        if is_expired or (days_left is not None and days_left <= 5):
            buttons.append([InlineKeyboardButton(
                text="🔄 Запросить продление",
                callback_data=f"proxy_extend_{user_id}_{index}"
            )])
    
    buttons.append([InlineKeyboardButton(
        text="🔙 К списку",
        callback_data="menu_proxy"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
