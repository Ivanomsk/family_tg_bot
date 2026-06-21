from aiogram import Router, F, types
from config import USER_PROXIES_FILE
from database.storage import load_json
from keyboards.inline import (
    get_proxy_main_keyboard,
    get_proxy_list_keyboard,
    get_proxy_empty_keyboard
)
from handlers.main_menu import require_private_chat

router = Router()

# ==========================================
# МЕНЮ ПРОКСИ
# ==========================================

@router.callback_query(F.data == "menu_proxy_main")
async def menu_proxy_main(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🛰 <b>Управление прокси</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_proxy_main_keyboard().as_markup()
    )


@router.callback_query(F.data == "menu_proxy")
async def menu_proxy(callback: types.CallbackQuery):
    if not await require_private_chat(callback, "просмотр прокси"):
        return
    
    await callback.answer()
    
    user_id = callback.from_user.id
    user_proxies = load_json(USER_PROXIES_FILE, {})
    proxies = user_proxies.get(str(user_id), {}).get("proxies", [])
    
    if not proxies:
        text = "🛰 <b>Мои прокси</b>\n\n"
        text += "У тебя пока нет прокси.\n\n"
        text += "Нажми кнопку ниже, чтобы запросить прокси у админа."
        
        await callback.message.edit_text(
            text,
            reply_markup=get_proxy_empty_keyboard().as_markup(),
            parse_mode="HTML"
        )
    else:
        text = f"🛰 <b>Мои прокси</b>\n\n"
        text += f"Найдено: <b>{len(proxies)}</b>\n"
        text += "Выбери прокси:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_proxy_list_keyboard(proxies, user_id).as_markup(),
            parse_mode="HTML"
        )