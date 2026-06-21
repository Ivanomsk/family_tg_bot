from datetime import datetime

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from repositories.vpn_repository import load_vpn_db

router = Router()

# ============================================
# ПОКАЗ ВСЕХ КОНФИГОВ ПОЛЬЗОВАТЕЛЯ
# ============================================

@router.callback_query(lambda c: c.data == "show_my_configs")
async def handle_show_my_configs(callback: types.CallbackQuery):
    """Обработчик кнопки 'Мои конфиги'"""
    user_id = callback.from_user.id
    vpn_users = load_vpn_db()
    
    if not vpn_users:
        await callback.message.answer("❌ Нет активных конфигов")
        await callback.answer()
        return
    
    user_configs = []
    for config_hash, config_data in vpn_users.items():
        if config_data.get('user_id') == user_id and config_data.get('active', True):
            user_configs.append({
                'hash': config_hash[:20],  # Короткий хеш для callback
                'username': config_data.get('username', 'unknown'),
                'expires_at': config_data.get('expires_at'),
                'days_left': None
            })
    
    if not user_configs:
        await callback.message.answer("❌ Нет активных конфигов")
        await callback.answer()
        return
    
    now = datetime.now()
    for config in user_configs:
        if config['expires_at']:
            try:
                expires_date = datetime.fromisoformat(config['expires_at'])
                config['days_left'] = (expires_date - now).days
            except:
                config['days_left'] = None
    
    await callback.message.edit_text(
        "📋 <b>Ваши VPN-конфиги:</b>\n\nВыберите конфиг:",
        parse_mode="HTML",
        reply_markup=get_my_configs_keyboard(user_id, user_configs).as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith('my_config_'))
async def handle_my_config_detail(callback: types.CallbackQuery):
    """Обработчик выбора конкретного конфига"""
    parts = callback.data.split('_', 2)
    if len(parts) < 3:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        user_id = int(parts[1])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    short_hash = parts[2]
    
    if callback.from_user.id != user_id:
        await callback.answer("⛔ Это не ваш конфиг!", show_alert=True)
        return
    
    # Ищем конфиг по короткому хешу
    vpn_users = load_vpn_db()
    config_hash = None
    config_data = None
    for ch, cd in vpn_users.items():
        if ch.startswith(short_hash) or ch[:20] == short_hash:
            config_hash = ch
            config_data = cd
            break
    
    if not config_data:
        await callback.answer("❌ Конфиг не найден", show_alert=True)
        return
    
    username = config_data.get('username', 'unknown')
    expires_at = config_data.get('expires_at', 'не указана')
    issued_at = config_data.get('issued_at', 'не указана')
    active = config_data.get('active', True)
    
    days_left = None
    is_expired = False
    if expires_at != 'не указана':
        try:
            expires_date = datetime.fromisoformat(expires_at)
            days_left = (expires_date - datetime.now()).days
            if days_left < 0:
                is_expired = True
        except:
            pass
    
    if is_expired or not active:
        status = "🔴 Истек / Неактивен"
    elif days_left is not None and days_left <= 3:
        status = f"🟡 Истекает через {days_left} дн."
    else:
        status = "🟢 Активен"
    
    text = (
        f"📋 <b>Детали конфига</b>\n\n"
        f"👤 <b>Имя:</b> {username}\n"
        f"📅 <b>Выдан:</b> {issued_at}\n"
        f"📅 <b>Истекает:</b> {expires_at}\n"
        f"📊 <b>Статус:</b> {status}\n"
    )
    
    if is_expired or not active:
        text += "\n\n🔴 <b>Конфиг просрочен!</b>\n"
        text += "Для продолжения использования запросите продление."
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_config_detail_keyboard_expired(user_id, config_hash[:20]).as_markup()
        )
    else:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_config_detail_keyboard(user_id, config_hash[:20], days_left or 999).as_markup()
        )
    
    await callback.answer()


@router.callback_query(lambda c: c.data == "refresh_my_configs")
async def handle_refresh_configs(callback: types.CallbackQuery):
    """Обновить список конфигов"""
    await handle_show_my_configs(callback)


# ============================================
# КОМАНДА /my_configs
# ============================================

@router.message(Command("my_configs"))
async def show_my_configs_command(message: types.Message):
    """Команда /my_configs"""
    user_id = message.from_user.id
    vpn_users = load_vpn_db()
    
    if not vpn_users:
        await message.answer("❌ Нет активных конфигов")
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
        await message.answer("❌ Нет активных конфигов")
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
        "📋 <b>Ваши VPN-конфиги:</b>\n\nВыберите конфиг:",
        parse_mode="HTML",
        reply_markup=get_my_configs_keyboard(user_id, user_configs).as_markup()
    )
