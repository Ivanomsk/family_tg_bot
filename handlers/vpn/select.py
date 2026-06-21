from aiogram import Router, F, types
from handlers.main_menu import require_private_chat

from handlers.vpn.common import logger, get_user_configs, get_user_dir
from repositories.vpn_repository import load_vpn_db

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from datetime import datetime

import os

router = Router()

# ==========================================
# ВЫБОР КОНФИГА (КАРТОЧКА)
# ==========================================

@router.callback_query(F.data.startswith("vpn_select_"))
async def vpn_select(callback: types.CallbackQuery):
    logger.info(f"?? vpn_select вызван с data: {callback.data}")
    
    if not await require_private_chat(callback, "просмотр VPN конфига"):
        return
    
    await callback.answer()
    
    username = callback.from_user.username
    if not username:
        await callback.message.answer("? Установите username в Telegram")
        return
    
    configs = get_user_configs(username)
    
    try:
        index = int(callback.data.split("_")[-1])
        conf_name = configs[index]
    except (IndexError, ValueError):
        await callback.answer("? Конфиг не найден", show_alert=True)
        return
    
    vpn_users = load_vpn_db()
    
    config_data = None
    config_hash = None
    for ch, cd in vpn_users.items():
        if cd.get('username') == username and cd.get('active', True):
            user_dir = get_user_dir(username)
            if os.path.exists(os.path.join(user_dir, conf_name)):
                config_data = cd
                config_hash = ch
                break
    
    user_id = callback.from_user.id
    config_index = index
    
    if config_data and config_hash:
        issued_at = config_data.get('issued_at', 'не указана')
        expires_at = config_data.get('expires_at', 'не указана')
        active = config_data.get('active', True)
        is_permanent = config_data.get('permanent', False)
        
        def format_date(date_str):
            if date_str == 'не указана':
                return date_str
            try:
                dt = datetime.fromisoformat(date_str)
                return dt.strftime('%d.%m.%Y %H:%M')
            except:
                try:
                    dt = datetime.strptime(date_str, '%d.%m.%Y')
                    return dt.strftime('%d.%m.%Y')
                except:
                    return date_str
        
        issued_display = format_date(issued_at)
        expires_display = format_date(expires_at)
        
        days_left = None
        is_expired = False
        if expires_at != 'не указана' and not is_permanent:
            try:
                expires_date = datetime.fromisoformat(expires_at)
                days_left = (expires_date - datetime.now()).days
                if days_left < 0:
                    is_expired = True
            except ValueError:
                try:
                    expires_date = datetime.strptime(expires_at, '%d.%m.%Y')
                    days_left = (expires_date - datetime.now()).days
                    if days_left < 0:
                        is_expired = True
                except:
                    pass
        
        if is_permanent:
            status = "?? Бессрочный"
        elif is_expired or not active:
            status = "?? Истек / Неактивен"
        elif days_left is not None and days_left <= 3:
            status = f"?? Истекает через {days_left} дн."
        else:
            status = "?? Активен"
        
        if is_permanent:
            text = (
                f"?? <b>Карточка конфига</b>\n\n"
                f"?? <b>Файл:</b> {conf_name}\n"
                f"?? <b>Выдан:</b> {issued_display}\n"
                f"?? <b>Статус:</b> {status}\n\n"
                f"?? <b>Бессрочный конфиг</b>\n"
                f"Срок действия не ограничен."
            )
        else:
            text = (
                f"?? <b>Карточка конфига</b>\n\n"
                f"?? <b>Файл:</b> {conf_name}\n"
                f"?? <b>Выдан:</b> {issued_display}\n"
                f"?? <b>Истекает:</b> {expires_display}\n"
                f"?? <b>Статус:</b> {status}\n"
            )
        
        if is_expired and not is_permanent:
            text += "\n\n?? <b>Конфиг просрочен!</b>\nСкачивание недоступно. Запросите продление."
        
        buttons = []
        
        if is_permanent or (not is_expired and active):
            buttons.append([InlineKeyboardButton(
                text="?? Скачать конфиг",
                callback_data=f"dwn_{user_id}_{config_index}"
            )])
        
        if not is_permanent:
            if (active and not is_expired and days_left is not None and days_left <= 5) or is_expired:
                buttons.append([InlineKeyboardButton(
                    text="?? Запросить продление",
                    callback_data=f"req_ext_{user_id}_{config_hash[:20]}"
                )])
        
        buttons.append([InlineKeyboardButton(
            text="?? К списку",
            callback_data="menu_vpn"
        )])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        text = (
            f"?? <b>Карточка конфига</b>\n\n"
            f"?? <b>Файл:</b> {conf_name}\n"
            f"?? <b>Статус:</b> ?? Активен\n\n"
            f"?? <i>Данные о конфиге отсутствуют в базе</i>"
        )
        
        buttons = [
            [InlineKeyboardButton(
                text="?? Скачать конфиг",
                callback_data=f"dwn_{user_id}_{config_index}"
            )],
            [InlineKeyboardButton(
                text="?? К списку",
                callback_data="menu_vpn"
            )]
        ]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
