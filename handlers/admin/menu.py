from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS, VPN_DIR, BACKUP_DIR
from utils.auto_delete import delete_admin, delete_temp
from utils.logger import standard_logger, audit_logger
from database.storage import load_json, save_json
from repositories.vpn_repository import load_vpn_db, save_vpn_db
from services.vpn_service import revoke_vpn_config
from handlers.common import get_user_dir, get_user_configs
from keyboards.inline import (
    get_back_keyboard,
    get_admin_main_keyboard,
    get_admin_users_keyboard,
    get_news_keyboard,
    get_amnezia_announce_keyboard,
    get_problem_cancel_keyboard
)
from handlers.main_menu import admin_private_only
import os
import re
import shutil
import tarfile
from datetime import datetime, timedelta

router = Router()
logger = standard_logger


# ==========================================
# АДМИН-ПАНЕЛЬ - КНОПКИ
# ==========================================

@router.callback_query(F.data == "menu_admin_main")
async def menu_admin_main(callback: types.CallbackQuery):
    """Админ-панель"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    await callback.message.edit_text(
        "⚙️ <b>Админ-панель</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_admin_main_keyboard().as_markup()
    )





