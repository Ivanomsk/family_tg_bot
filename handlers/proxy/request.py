from aiogram import Router, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMIN_IDS
from handlers.main_menu import require_private_chat

router = Router()

# ==========================================
# ЗАПРОС НОВОГО ПРОКСИ
# ==========================================

@router.callback_query(F.data == "proxy_request")
async def proxy_request(callback: types.CallbackQuery):
    if not await require_private_chat(callback, "запрос прокси"):
        return
    
    await callback.answer()
    
    user = callback.from_user
    username = user.username or f"ID:{user.id}"
    
    request_msg = (
        f"🛰 <b>НОВЫЙ ЗАПРОС ПРОКСИ</b>\n\n"
        f"👤 @{username}\n"
        f"📱 ID: {user.id}\n\n"
        f"Ждёт персональный прокси-ключ!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📝 Выписать ключ",
                callback_data=f"proxy_issue_{user.id}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"proxy_reject_{user.id}"
            )
        ]
    ])
    
    sent_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                request_msg,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")
    
    text = (
        "✅ <b>Запрос отправлен!</b>\n\n"
        f"Админ получил твою заявку.\n"
        f"Ожидай ответа...\n\n"
        f"💡 <i>Отправлено {sent_count} админу(ам)</i>"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_proxy_request_keyboard().as_markup(),
        parse_mode="HTML"
    )
