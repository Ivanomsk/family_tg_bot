from repositories.vpn_repository import load_vpn_db
from aiogram import Router, F, types
from aiogram.filters import Command
from handlers.vpn.common import logger, get_user_configs, get_user_dir

from utils.auto_delete import delete_temp

from aiogram.types import FSInputFile

import os

router = Router()

# ==========================================
# СКАЧИВАНИЕ КОНФИГА
# ==========================================

@router.callback_query(F.data.startswith("dwn_"))
async def download_config(callback: types.CallbackQuery):
    logger.info(f"?? download_config ВЫЗВАН с data: {callback.data}")
    await callback.answer()
    
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("? Ошибка", show_alert=True)
        return
    
    try:
        user_id = int(parts[1])
        config_index = int(parts[2])
    except ValueError:
        await callback.answer("? Ошибка", show_alert=True)
        return
    
    if callback.from_user.id != user_id:
        await callback.answer("? Не ваш конфиг!", show_alert=True)
        return
    
    username = callback.from_user.username
    if not username:
        await callback.answer("? Нет username", show_alert=True)
        return
    
    configs = get_user_configs(username)
    
    try:
        conf_name = configs[config_index]
    except IndexError:
        await callback.answer("? Конфиг не найден", show_alert=True)
        return
    
    vpn_users = load_vpn_db()
    is_expired = False
    is_permanent = False
    for ch, cd in vpn_users.items():
        if cd.get('username') == username and cd.get('active', True):
            if cd.get('permanent', False):
                is_permanent = True
                break
            expires_at = cd.get('expires_at')
            if expires_at:
                try:
                    expires_date = datetime.fromisoformat(expires_at)
                    if expires_date < datetime.now():
                        is_expired = True
                        break
                except:
                    pass
    
    if is_expired and not is_permanent:
        await callback.answer("?? Конфиг просрочен! Скачивание недоступно.", show_alert=True)
        return
    
    user_dir = get_user_dir(username)
    file_path = os.path.join(user_dir, conf_name)
    
    if os.path.exists(file_path):
        await callback.message.answer_document(
            document=FSInputFile(file_path, filename=conf_name),
            caption=f"?? <b>{conf_name}</b>",
            parse_mode="HTML"
        )
    else:
        await callback.answer("? Файл не найден", show_alert=True)

# ==========================================
# КОМАНДА /my_configs
# ==========================================

@router.message(Command("my_configs"))
async def show_my_configs_command(message: types.Message):
    user_id = message.from_user.id
    vpn_users = load_vpn_db()
    
    if not vpn_users:
        await message.answer("? Нет активных конфигов")
        return
    
    user_configs = []
    for config_hash, config_data in vpn_users.items():
        if config_data.get('user_id') == user_id and config_data.get('active', True):
            user_configs.append({
                'hash': config_hash[:20],
                'username': config_data.get('username', 'unknown'),
                'expires_at': config_data.get('expires_at'),
                'days_left': None
            })
    
    if not user_configs:
        await message.answer("? Нет активных конфигов")
        return
    
    now = datetime.now()
    for config in user_configs:
        if config['expires_at']:
            try:
                expires_date = datetime.fromisoformat(config['expires_at'])
                config['days_left'] = (expires_date - now).days
            except:
                config['days_left'] = None
    
    await message.answer(
        "?? <b>Ваши VPN-конфиги:</b>\n\nВыберите конфиг:",
        parse_mode="HTML",
        reply_markup=get_my_configs_keyboard(user_id, user_configs).as_markup()
    )
