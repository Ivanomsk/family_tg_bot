from aiogram import Router, types, F
from config import ADMIN_IDS
from utils.logger import standard_logger
from repositories.vpn_repository import load_vpn_db
from database.storage import load_json
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


