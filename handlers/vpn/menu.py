from aiogram import Router, F, types
from handlers.main_menu import require_private_chat
from utils.auto_delete import delete_temp
from repositories.vpn_repository import load_vpn_db
from keyboards.inline import *
from handlers.vpn.common import logger, get_user_configs

router = Router()

# ==========================================
# МЕНЮ VPN
# ==========================================

@router.callback_query(F.data == "menu_vpn_main")
async def menu_vpn_main(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "?? <b>Управление VPN</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_vpn_main_keyboard().as_markup()
    )


@router.callback_query(F.data == "menu_vpn")
async def menu_vpn(callback: types.CallbackQuery):
    if not await require_private_chat(callback, "просмотр VPN конфигов"):
        return
    
    await callback.answer()
    
    username = callback.from_user.username
    logger.info(f"?? Запрос конфигов для пользователя: {username}")
    
    if not username:
        msg = await callback.message.answer(
            "? <b>Установи username!</b>\n\n"
            "Зайди в настройки Telegram и укажи имя пользователя.",
            reply_markup=get_back_to_main_menu().as_markup(),
            parse_mode="HTML"
        )
        delete_temp(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)
        return
    
    configs = get_user_configs(username)
    logger.info(f"?? Найдено конфигов: {len(configs)} для пользователя {username}")
    
    if not configs:
        vpn_users = load_vpn_db()
        user_configs = []
        for config_hash, config_data in vpn_users.items():
            if config_data.get('user_id') == callback.from_user.id and config_data.get('active', True):
                user_configs.append(config_data.get('username', ''))
        
        if user_configs:
            text = f"?? <b>VPN конфиги</b>\n\n"
            text += f"@{username}, у тебя есть конфиги в базе, но файлы отсутствуют.\n\n"
            text += "Нажми кнопку ниже, чтобы запросить новый конфиг у админа."
        else:
            text = f"?? <b>VPN конфиги</b>\n\n"
            text += f"@{username}, у тебя пока нет конфигов.\n\n"
            text += "Нажми кнопку ниже, чтобы запросить новый конфиг у админа."
        
        await callback.message.edit_text(
            text,
            reply_markup=get_vpn_empty_keyboard().as_markup(),
            parse_mode="HTML"
        )
    else:
        text = f"?? <b>VPN конфиги</b>\n\n"
        text += f"@{username}, найдено: <b>{len(configs)}</b>\n"
        text += "Выбери или запроси новый:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_vpn_list_keyboard(configs, username).as_markup(),
            parse_mode="HTML"
        )
