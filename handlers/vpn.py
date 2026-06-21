from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_IDS, VPN_DIR
from utils.auto_delete import delete_temp
from utils.logger import standard_logger, audit_logger
from database.storage import load_json, save_json
from repositories.vpn_repository import load_vpn_db
from keyboards.inline import (
    get_vpn_main_keyboard,
    get_vpn_list_keyboard,
    get_vpn_empty_keyboard,
    get_vpn_request_keyboard,
    get_admin_vpn_request_keyboard,
    get_back_keyboard,
    get_config_detail_keyboard,
    get_config_detail_keyboard_expired,
    get_my_configs_keyboard
)
from states.forms import ConfigRequest
from handlers.main_menu import require_private_chat
import os
import re
from datetime import datetime, timedelta

router = Router()
logger = standard_logger


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def get_user_dir(username: str) -> str:
    safe_name = re.sub(r'[^\w\-]', '_', username)
    path = os.path.join(VPN_DIR, safe_name)
    os.makedirs(path, exist_ok=True)
    return path


def get_user_configs(username: str) -> list:
    if not username:
        return []
    user_dir = get_user_dir(username)
    try:
        files = [f for f in os.listdir(user_dir) if f.endswith('.vpn')]
        logger.info(f"📁 Сканируем папку {user_dir}: найдено {len(files)} файлов: {files}")
        return sorted(files)
    except Exception as e:
        logger.error(f"Ошибка сканирования папки {user_dir}: {e}")
        return []


# ==========================================
# МЕНЮ VPN
# ==========================================

@router.callback_query(F.data == "menu_vpn_main")
async def menu_vpn_main(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🔐 <b>Управление VPN</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_vpn_main_keyboard().as_markup()
    )


@router.callback_query(F.data == "menu_vpn")
async def menu_vpn(callback: types.CallbackQuery):
    if not await require_private_chat(callback, "просмотр VPN конфигов"):
        return
    
    await callback.answer()
    
    username = callback.from_user.username
    logger.info(f"🔍 Запрос конфигов для пользователя: {username}")
    
    if not username:
        msg = await callback.message.answer(
            "❌ <b>Установи username!</b>\n\n"
            "Зайди в настройки Telegram и укажи имя пользователя.",
            reply_markup=get_back_to_main_menu().as_markup(),
            parse_mode="HTML"
        )
        delete_temp(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)
        return
    
    configs = get_user_configs(username)
    logger.info(f"📁 Найдено конфигов: {len(configs)} для пользователя {username}")
    
    if not configs:
        vpn_users = load_vpn_db()
        user_configs = []
        for config_hash, config_data in vpn_users.items():
            if config_data.get('user_id') == callback.from_user.id and config_data.get('active', True):
                user_configs.append(config_data.get('username', ''))
        
        if user_configs:
            text = f"🔐 <b>VPN конфиги</b>\n\n"
            text += f"@{username}, у тебя есть конфиги в базе, но файлы отсутствуют.\n\n"
            text += "Нажми кнопку ниже, чтобы запросить новый конфиг у админа."
        else:
            text = f"🔐 <b>VPN конфиги</b>\n\n"
            text += f"@{username}, у тебя пока нет конфигов.\n\n"
            text += "Нажми кнопку ниже, чтобы запросить новый конфиг у админа."
        
        await callback.message.edit_text(
            text,
            reply_markup=get_vpn_empty_keyboard().as_markup(),
            parse_mode="HTML"
        )
    else:
        text = f"🔐 <b>VPN конфиги</b>\n\n"
        text += f"@{username}, найдено: <b>{len(configs)}</b>\n"
        text += "Выбери или запроси новый:"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_vpn_list_keyboard(configs, username).as_markup(),
            parse_mode="HTML"
        )


# ==========================================
# ВЫБОР КОНФИГА (КАРТОЧКА)
# ==========================================

@router.callback_query(F.data.startswith("vpn_select_"))
async def vpn_select(callback: types.CallbackQuery):
    logger.info(f"🔍 vpn_select вызван с data: {callback.data}")
    
    if not await require_private_chat(callback, "просмотр VPN конфига"):
        return
    
    await callback.answer()
    
    username = callback.from_user.username
    if not username:
        await callback.message.answer("❌ Установите username в Telegram")
        return
    
    configs = get_user_configs(username)
    
    try:
        index = int(callback.data.split("_")[-1])
        conf_name = configs[index]
    except (IndexError, ValueError):
        await callback.answer("❌ Конфиг не найден", show_alert=True)
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
            status = "♾️ Бессрочный"
        elif is_expired or not active:
            status = "🔴 Истек / Неактивен"
        elif days_left is not None and days_left <= 3:
            status = f"🟡 Истекает через {days_left} дн."
        else:
            status = "🟢 Активен"
        
        if is_permanent:
            text = (
                f"📋 <b>Карточка конфига</b>\n\n"
                f"📁 <b>Файл:</b> {conf_name}\n"
                f"📅 <b>Выдан:</b> {issued_display}\n"
                f"📊 <b>Статус:</b> {status}\n\n"
                f"♾️ <b>Бессрочный конфиг</b>\n"
                f"Срок действия не ограничен."
            )
        else:
            text = (
                f"📋 <b>Карточка конфига</b>\n\n"
                f"📁 <b>Файл:</b> {conf_name}\n"
                f"📅 <b>Выдан:</b> {issued_display}\n"
                f"📅 <b>Истекает:</b> {expires_display}\n"
                f"📊 <b>Статус:</b> {status}\n"
            )
        
        if is_expired and not is_permanent:
            text += "\n\n🔴 <b>Конфиг просрочен!</b>\nСкачивание недоступно. Запросите продление."
        
        buttons = []
        
        if is_permanent or (not is_expired and active):
            buttons.append([InlineKeyboardButton(
                text="📥 Скачать конфиг",
                callback_data=f"dwn_{user_id}_{config_index}"
            )])
        
        if not is_permanent:
            if (active and not is_expired and days_left is not None and days_left <= 5) or is_expired:
                buttons.append([InlineKeyboardButton(
                    text="🔄 Запросить продление",
                    callback_data=f"req_ext_{user_id}_{config_hash[:20]}"
                )])
        
        buttons.append([InlineKeyboardButton(
            text="🔙 К списку",
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
            f"📋 <b>Карточка конфига</b>\n\n"
            f"📁 <b>Файл:</b> {conf_name}\n"
            f"📊 <b>Статус:</b> 🟢 Активен\n\n"
            f"💡 <i>Данные о конфиге отсутствуют в базе</i>"
        )
        
        buttons = [
            [InlineKeyboardButton(
                text="📥 Скачать конфиг",
                callback_data=f"dwn_{user_id}_{config_index}"
            )],
            [InlineKeyboardButton(
                text="🔙 К списку",
                callback_data="menu_vpn"
            )]
        ]
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )


# ==========================================
# СКАЧИВАНИЕ КОНФИГА
# ==========================================

@router.callback_query(F.data.startswith("dwn_"))
async def download_config(callback: types.CallbackQuery):
    logger.info(f"🔍 download_config ВЫЗВАН с data: {callback.data}")
    await callback.answer()
    
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        user_id = int(parts[1])
        config_index = int(parts[2])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    if callback.from_user.id != user_id:
        await callback.answer("⛔ Не ваш конфиг!", show_alert=True)
        return
    
    username = callback.from_user.username
    if not username:
        await callback.answer("❌ Нет username", show_alert=True)
        return
    
    configs = get_user_configs(username)
    
    try:
        conf_name = configs[config_index]
    except IndexError:
        await callback.answer("❌ Конфиг не найден", show_alert=True)
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
        await callback.answer("🔴 Конфиг просрочен! Скачивание недоступно.", show_alert=True)
        return
    
    user_dir = get_user_dir(username)
    file_path = os.path.join(user_dir, conf_name)
    
    if os.path.exists(file_path):
        await callback.message.answer_document(
            document=FSInputFile(file_path, filename=conf_name),
            caption=f"📁 <b>{conf_name}</b>",
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Файл не найден", show_alert=True)


# ==========================================
# ЗАПРОС НОВОГО VPN
# ==========================================

@router.callback_query(F.data == "vpn_request")
async def vpn_request(callback: types.CallbackQuery, state: FSMContext):
    if not await require_private_chat(callback, "запрос VPN"):
        return
    await callback.answer()
    await state.set_state(ConfigRequest.waiting_for_device)
    await callback.message.edit_text(
        "🔄 <b>Запрос нового VPN конфига</b>\n\n"
        "Для какого устройства нужен конфиг?\n\n"
        "Напиши название (например: iPhone, MacBook, Android)\n\n"
        "Или нажми кнопку отмены.",
        reply_markup=get_vpn_request_keyboard().as_markup(),
        parse_mode="HTML"
    )


@router.message(ConfigRequest.waiting_for_device, F.text)
async def process_vpn_device(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Запрос отменён.", reply_markup=get_back_to_main_menu().as_markup())
        return
    
    device = message.text.strip()
    user = message.from_user
    username = user.username or f"ID:{user.id}"
    
    requests = load_json("bot_data/vpn_requests.json", {})
    requests[str(user.id)] = {
        "username": username,
        "device": device,
        "timestamp": datetime.now().isoformat()
    }
    save_json("bot_data/vpn_requests.json", requests)
    
    request_msg = (
        f"🔔 <b>НОВЫЙ ЗАПРОС VPN</b>\n\n"
        f"👤 @{username}\n"
        f"📱 ID: {user.id}\n"
        f"💬 Устройство: {device}"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                request_msg,
                reply_markup=get_admin_vpn_request_keyboard(user.id).as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")
    
    await message.answer(
        "✅ <b>Запрос отправлен админу!</b>\n\nОжидай ответа.",
        reply_markup=get_back_to_main_menu().as_markup(),
        parse_mode="HTML"
    )
    await state.clear()


# ==========================================
# КОМАНДА /my_configs
# ==========================================

@router.message(Command("my_configs"))
async def show_my_configs_command(message: types.Message):
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
