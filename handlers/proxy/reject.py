from aiogram import Router, F, types

from config import ADMIN_IDS

router = Router()

@router.callback_query(F.data.startswith("proxy_reject_"))
async def proxy_reject(callback: types.CallbackQuery):
    """Админ отклоняет запрос прокси"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[-1])
    
    try:
        await callback.bot.send_message(
            user_id,
            "❌ <b>Запрос прокси отклонён</b>\n\nОбратитесь к администратору.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    await callback.message.edit_text("❌ Запрос отклонён")
    await callback.answer()