from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS, USER_PROXIES_FILE, VPN_DIR, BACKUP_DIR
from utils.auto_delete import delete_user, delete_admin, delete_temp
from utils.stats import update_stats
from utils.expiry import get_vpn_config_age, get_proxy_age
from database.storage import load_json, save_json
from keyboards.inline import (
    get_main_menu_keyboard,
    get_back_to_main_menu,
    get_vpn_list_keyboard,
    get_vpn_empty_keyboard,
    get_vpn_request_keyboard,
    get_admin_vpn_request_keyboard,
    get_proxy_list_keyboard,
    get_proxy_empty_keyboard,
    get_proxy_detail_keyboard,
    get_proxy_card_keyboard,
    get_proxy_request_keyboard,
    get_admin_proxy_request_keyboard,
    get_help_keyboard
)
from states.forms import ConfigRequest, ProxyRequest
import os
import re
import logging
import asyncio
from datetime import datetime

router = Router()
logger = logging.getLogger(__name__)

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
        return sorted([f for f in os.listdir(user_dir) if f.endswith('.vpn')])
    except Exception:
        return []

async def require_private_chat(callback: types.CallbackQuery, feature_name: str = "эта функция") -> bool:
    """Проверка, что callback в ЛС. Возвращает False если нужно прекратить."""
    if callback.message.chat.type != "private":
        # Получаем username бота
        bot_info = await callback.bot.get_me()
        bot_username = bot_info.username
        
        # Создаём клавиатуру с кнопкой-ссылкой
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="💬 Открыть чат с ботом", url=f"https://t.me/{bot_username}")
        builder.adjust(1)
        
        # Отправляем сообщение с ошибкой
        msg = await callback.message.answer(
            f"❌ <b>{feature_name.capitalize()} доступна только в личных сообщениях!</b>\n\n"
            f"👉 Нажмите кнопку ниже, чтобы перейти в ЛС:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
        # ✅ Автоудаление через 30 секунд (allow_group=True для групповых чатов)
        delete_temp(
            callback.message.bot, 
            callback.message.chat.id, 
            msg.message_id, 
            user_id=callback.from_user.id, 
            chat_type=callback.message.chat.type,
            allow_group=True
        )
        
        return False
    return True

# ==========================================
# КОМАНДЫ
# ==========================================

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    update_stats(message.from_user, "start")
    is_admin = message.from_user.id in ADMIN_IDS
    
    text = (
        "👋 <b>Привет! Я Санитар Дурдома.</b>\n\n"
        "Я помогу управлять VPN конфигами и персональными прокси.\n"
        "Выбери нужный раздел ниже:"
    )
    
    msg = await message.answer(
        text, 
        reply_markup=get_main_menu_keyboard(is_admin).as_markup(), 
        parse_mode="HTML"
    )
    
    if is_admin:
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
    else:
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.message(Command("ping"))
async def cmd_ping(message: types.Message):
    msg = await message.answer("🏓 <b>Pong!</b>\nБот работает стабильно.", parse_mode="HTML")
    delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.callback_query(F.data == "menu_ping")
async def menu_ping(callback: types.CallbackQuery):
    """Кнопка проверки связи"""
    await callback.answer()
    
    msg = await callback.message.answer(
        "🏓 <b>Pong!</b>\n\n"
        "✅ Бот работает стабильно\n"
        "⚡ Время отклика: мгновенно",
        parse_mode="HTML"
    )
    
    # Автоудаление через 30 секунд (работает и в группе)
    delete_temp(
        callback.message.bot, 
        callback.message.chat.id, 
        msg.message_id, 
        user_id=callback.from_user.id, 
        chat_type=callback.message.chat.type,
        allow_group=True
    )

# ==========================================
# ГЛАВНОЕ МЕНЮ - КНОПКИ
# ==========================================

@router.callback_query(F.data == "menu_main")
async def menu_main(callback: types.CallbackQuery):
    """Главное меню"""
    await callback.answer()
    is_admin = callback.from_user.id in ADMIN_IDS
    
    text = (
        "👋 <b>Главное меню</b>\n\n"
        "Выбери раздел:"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_main_menu_keyboard(is_admin).as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "menu_vpn")
async def menu_vpn(callback: types.CallbackQuery):
    """Меню VPN конфигов"""
    # 🔒 ПРОВЕРКА: только в ЛС!
    if not await require_private_chat(callback, "просмотр VPN конфигов"):
        return
    
    await callback.answer()
    
    username = callback.from_user.username
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
    
    if not configs:
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

@router.callback_query(F.data == "menu_proxy")
async def menu_proxy(callback: types.CallbackQuery):
    """Меню прокси"""
    # 🔒 ПРОВЕРКА: только в ЛС!
    if not await require_private_chat(callback, "управление прокси"):
        return
    
    await callback.answer()
    
    user_id = callback.from_user.id
    user_proxies = load_json(USER_PROXIES_FILE, {})
    proxies = user_proxies.get(str(user_id), {}).get("proxies", [])
    
    if not proxies:
        text = f"🛰 <b>Мои прокси</b>\n\n"
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

# ==========================================
# СПРАВКА И АДМИНКА
# ==========================================

@router.callback_query(F.data == "menu_help")
async def menu_help(callback: types.CallbackQuery):
    """Справка — интерактивное меню"""
    await callback.answer()
    
    is_admin = callback.from_user.id in ADMIN_IDS
    
    text = (
        "📖 <b>СПРАВОЧНИК</b>\n\n"
        "Выберите раздел:\n\n"
        "<b>📱 Пользователю:</b>\n"
        "• Как получить VPN\n"
        "• Как запросить прокси\n"
        "• Как подключить прокси"
    )
    
    if is_admin:
        text += "\n\n" + "━" * 20 + "\n\n<b>⚙️ Админу:</b>\n" + "• Управление системой"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔐 Как получить VPN", callback_data="help_vpn_info")
    builder.button(text="🛰 Как запросить прокси", callback_data="help_proxy_info")
    builder.button(text="👁 Как подключить прокси", callback_data="help_connect_info")
    
    if is_admin:
        builder.button(text="⚙️ Администрирование", callback_data="menu_admin")
    
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(1)
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "help_vpn_info")
async def help_vpn_info(callback: types.CallbackQuery):
    """Справка по VPN"""
    await callback.answer()
    
    text = (
        "🔐 <b>КАК ПОЛУЧИТЬ VPN</b>\n\n"
        "<b>Шаг 1:</b> Нажми кнопку «VPN конфиги»\n"
        "<b>Шаг 2:</b> Если конфигов нет — нажми «Запросить новый конфиг»\n"
        "<b>Шаг 3:</b> Напиши название устройства (iPhone, MacBook и т.д.)\n"
        "<b>Шаг 4:</b> Админ получит запрос и загрузит конфиг\n"
        "<b>Шаг 5:</b> Ты получишь файл .vpn для подключения\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 <i>Конфиги действуют 30 дней. Перед истечением срока бот напомнит!</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад к справке", callback_data="menu_help")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "help_proxy_info")
async def help_proxy_info(callback: types.CallbackQuery):
    """Справка по запросу прокси"""
    await callback.answer()
    
    text = (
        "🛰 <b>КАК ЗАПРОСИТЬ ПРОКСИ</b>\n\n"
        "<b>Шаг 1:</b> Нажми кнопку «Мои прокси»\n"
        "<b>Шаг 2:</b> Если прокси нет — нажми «Запросить прокси»\n"
        "<b>Шаг 3:</b> Админ получит твою заявку\n"
        "<b>Шаг 4:</b> Админ создаст персональный прокси-ключ\n"
        "<b>Шаг 5:</b> Ты получишь данные для подключения\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 <i>Прокси действуют 30 дней. Бот предупредит об истечении!</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад к справке", callback_data="menu_help")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "help_connect_info")
async def help_connect_info(callback: types.CallbackQuery):
    """Справка по подключению прокси"""
    await callback.answer()
    
    text = (
        "👁 <b>КАК ПОДКЛЮЧИТЬ ПРОКСИ</b>\n\n"
        "<b>Способ 1 (быстрый):</b>\n"
        "1. Открой «Мои прокси»\n"
        "2. Выбери нужный прокси\n"
        "3. Нажми кнопку «📱 Подключить в Telegram»\n"
        "4. Подтверди подключение\n\n"
        "<b>Способ 2 (вручную):</b>\n"
        "1. Открой «Мои прокси»\n"
        "2. Выбери прокси\n"
        "3. Скопируй данные (Сервер, Порт, Секрет)\n"
        "4. Настройки → Данные и память → Прокси\n"
        "5. Добавить прокси → MTProto\n"
        "6. Вставь данные\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💡 <i>Кнопка «Подключить» работает только в Telegram!</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад к справке", callback_data="menu_help")
    builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "menu_admin")
async def menu_admin(callback: types.CallbackQuery):
    """Административное меню"""
    # 🔒 ПРОВЕРКА: только админ!
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    
    # 🔒 ПРОВЕРКА: только в ЛС!
    if not await require_private_chat(callback, "администрирование"):
        return
    
    await callback.answer()
    
    text = (
        "⚙️ <b>АДМИНИСТРИРОВАНИЕ</b>\n\n"
        "Выберите раздел:\n\n"
        "📊 <b>Мониторинг:</b>\n"
        "• Статистика использования\n"
        "• Проверка сроков VPN/прокси\n\n"
        "📂 <b>Управление:</b>\n"
        "• Конфиги пользователей\n"
        "• Управление прокси\n\n"
        "💾 <b>Резервное копирование:</b>\n"
        "• Создать бэкап\n"
        "• Список бэкапов\n"
        "• Очистка старых"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="🔍 Проверка сроков", callback_data="admin_check_expiry")
    builder.button(text="📂 Конфиги пользователей", callback_data="admin_user_configs")
    builder.button(text="🛰 Управление прокси", callback_data="admin_proxy_manage")
    builder.button(text="📦 Создать бэкап", callback_data="admin_backup_create")
    builder.button(text="📋 Список бэкапов", callback_data="admin_backup_list")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(1)
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    """Статистика"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    
    if not await require_private_chat(callback, "статистика"):
        return
    
    await callback.answer()
    
    stats = load_json("bot_data/stats.json", {})
    if not stats:
        text = "📊 Статистики пока нет."
        await callback.message.edit_text(
            text,
            reply_markup=get_back_to_main_menu().as_markup(),
            parse_mode="HTML"
        )
        return
    
    user_proxies = load_json(USER_PROXIES_FILE, {})
    
    text = "📊 <b>Статистика использования:</b>\n\n"
    sorted_users = sorted(stats.items(), key=lambda x: sum(x[1].get("actions", {}).values()), reverse=True)
    
    for uid, data in sorted_users[:10]:
        username = data.get("username") or "Unknown"
        name = data.get("name") or username
        total = sum(data.get("actions", {}).values())
        vpn = data.get("actions", {}).get("vpn", 0)
        proxy_count = len(user_proxies.get(uid, {}).get("proxies", []))
        
        text += f"👤 <b>{name}</b>\n"
        text += f"   Действий: {total} | VPN: {vpn} | Прокси: {proxy_count}\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="menu_admin")
    builder.adjust(1)
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_check_expiry")
async def admin_check_expiry(callback: types.CallbackQuery):
    """Проверка сроков"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    
    if not await require_private_chat(callback, "проверка сроков"):
        return
    
    await callback.answer()
    
    from utils.expiry import check_all_vpn_expiry, check_all_proxy_expiry
    
    vpn_expired, vpn_expiring = check_all_vpn_expiry()
    proxy_expired, proxy_expiring = check_all_proxy_expiry()
    
    text = "🔍 <b>ПРОВЕРКА СРОКОВ</b>\n\n"
    
    if vpn_expired:
        text += f"❌ <b>VPN истекли ({len(vpn_expired)}):</b>\n"
        for item in vpn_expired[:5]:
            text += f"  • @{item['username']} — {item['filename']}\n"
        text += "\n"
    
    if vpn_expiring:
        text += f"⚠️ <b>VPN истекают ({len(vpn_expiring)}):</b>\n"
        for item in vpn_expiring[:5]:
            text += f"  • @{item['username']} — {item['filename']} ({item['days_left']} дн.)\n"
        text += "\n"
    
    if proxy_expired:
        text += f"❌ <b>Прокси истекли ({len(proxy_expired)}):</b>\n"
        for item in proxy_expired[:5]:
            text += f"  • ID {item['user_id']} — {item['proxy_name']}\n"
        text += "\n"
    
    if proxy_expiring:
        text += f"⚠️ <b>Прокси истекают ({len(proxy_expiring)}):</b>\n"
        for item in proxy_expiring[:5]:
            text += f"  • ID {item['user_id']} — {item['proxy_name']} ({item['days_left']} дн.)\n"
        text += "\n"
    
    if not (vpn_expired or vpn_expiring or proxy_expired or proxy_expiring):
        text += "✅ Всё активно! Истёкших и истекающих нет.\n"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="menu_admin")
    builder.adjust(1)
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_user_configs")
async def admin_user_configs(callback: types.CallbackQuery):
    """Управление конфигами пользователей"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    
    if not await require_private_chat(callback, "управление конфигами"):
        return
    
    await callback.answer()
    
    text = (
        "📂 <b>УПРАВЛЕНИЕ КОНФИГАМИ</b>\n\n"
        "💡 <b>Используй команды:</b>\n\n"
        "<code>/configs</code> — список всех конфигов\n"
        "<code>/delconfig username файл.vpn</code> — удалить конфиг\n"
        "<code>/clearuser username</code> — удалить все конфиги\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 <i>Нажми на команду чтобы скопировать</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="menu_admin")
    builder.adjust(1)
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_proxy_manage")
async def admin_proxy_manage(callback: types.CallbackQuery):
    """Управление прокси"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    
    if not await require_private_chat(callback, "управление прокси"):
        return
    
    await callback.answer()
    
    text = (
        "🛰 <b>УПРАВЛЕНИЕ ПРОКСИ</b>\n\n"
        "💡 <b>Используй команды:</b>\n\n"
        "<code>/clearproxy username</code> — удалить все прокси пользователя\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 <i>Нажми на команду чтобы скопировать</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="menu_admin")
    builder.adjust(1)
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_backup_create")
async def admin_backup_create(callback: types.CallbackQuery):
    """Создание бэкапа"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    
    if not await require_private_chat(callback, "создание бэкапа"):
        return
    
    await callback.answer()
    
    text = (
        "📦 <b>СОЗДАНИЕ БЭКАПА</b>\n\n"
        "💡 <b>Используй команду:</b>\n\n"
        "<code>/backup</code> — создать резервную копию\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🤖 <b>Автобэкап:</b>\n"
        "• Каждый день в 03:00\n"
        "• Хранится 7 последних\n"
        "• Уведомление приходит в ЛС\n\n"
        "📝 <i>Нажми на команду чтобы скопировать</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="menu_admin")
    builder.adjust(1)
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "admin_backup_list")
async def admin_backup_list(callback: types.CallbackQuery):
    """Список бэкапов"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    
    if not await require_private_chat(callback, "список бэкапов"):
        return
    
    await callback.answer()
    
    text = (
        "📋 <b>СПИСОК БЭКАПОВ</b>\n\n"
        "💡 <b>Используй команды:</b>\n\n"
        "<code>/list_backups</code> — показать все бэкапы\n"
        "<code>/delete_backup filename.tar.gz</code> — удалить бэкап\n"
        "<code>/cleanup_backups 5</code> — оставить 5 последних\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 <i>Нажми на команду чтобы скопировать</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="menu_admin")
    builder.adjust(1)
    
    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

# ==========================================
# VPN - ВЫБОР КОНФИГА
# ==========================================

@router.callback_query(F.data.startswith("vpn_select_"))
async def vpn_select(callback: types.CallbackQuery):
    """Выбор конкретного VPN конфига"""
    # 🔒 ПРОВЕРКА: только в ЛС!
    if not await require_private_chat(callback, "скачивание VPN конфига"):
        return
    
    await callback.answer()
    
    username = callback.from_user.username
    configs = get_user_configs(username)
    
    try:
        index = int(callback.data.split("_")[-1])
        conf_name = configs[index]
    except (IndexError, ValueError):
        await callback.answer("❌ Конфиг не найден", show_alert=True)
        return
    
    user_dir = get_user_dir(username)
    file_path = os.path.join(user_dir, conf_name)
    
    if os.path.exists(file_path):
        # ✅ ИСПРАВЛЕНО: добавлен parse_mode="HTML"
        await callback.message.answer_document(
            document=FSInputFile(file_path, filename=conf_name),
            caption=f"🔐 <b>{conf_name.replace('.vpn', '')}</b>",
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Файл не найден", show_alert=True)

@router.callback_query(F.data == "vpn_send_all")
async def vpn_send_all(callback: types.CallbackQuery):
    """Отправить все конфиги"""
    # 🔒 ПРОВЕРКА: только в ЛС!
    if not await require_private_chat(callback, "отправка всех конфигов"):
        return
    
    await callback.answer()
    
    username = callback.from_user.username
    configs = get_user_configs(username)
    
    if not configs:
        await callback.answer("❌ Нет конфигов", show_alert=True)
        return
    
    msg = await callback.message.answer(f"📦 Отправляю {len(configs)} конфигов...")
    
    user_dir = get_user_dir(username)
    sent = 0
    
    for conf in configs:
        file_path = os.path.join(user_dir, conf)
        if os.path.exists(file_path):
            try:
                # ✅ ИСПРАВЛЕНО: добавлен parse_mode="HTML"
                await callback.message.answer_document(
                    document=FSInputFile(file_path, filename=conf),
                    caption=f"🔹 <b>{conf.replace('.vpn', '')}</b>",
                    parse_mode="HTML"
                )
                sent += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Ошибка отправки {conf}: {e}")
    
    await msg.delete()
    await callback.message.answer(f"✅ Отправлено: {sent}/{len(configs)}")

@router.callback_query(F.data == "vpn_request")
async def vpn_request(callback: types.CallbackQuery, state: FSMContext):
    """Запрос нового VPN конфига"""
    # 🔒 ПРОВЕРКА: только в ЛС!
    if not await require_private_chat(callback, "запрос VPN"):
        return
    
    await callback.answer()
    await state.set_state(ConfigRequest.waiting_for_device)
    
    text = (
        "🔄 <b>Запрос нового VPN конфига</b>\n\n"
        "Для какого устройства нужен конфиг?\n\n"
        "Напиши название (например: iPhone, MacBook, Android)\n\n"
        "Или нажми кнопку отмены."
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_vpn_request_keyboard().as_markup(),
        parse_mode="HTML"
    )

# ==========================================
# ПРОКСИ - ВЫБОР
# ==========================================

@router.callback_query(F.data.startswith("proxy_select_"))
async def proxy_select(callback: types.CallbackQuery):
    """Выбор конкретного прокси"""
    # 🔒 ПРОВЕРКА: только в ЛС!
    if not await require_private_chat(callback, "просмотр данных прокси"):
        return
    
    await callback.answer()
    
    user_id = callback.from_user.id
    user_proxies = load_json(USER_PROXIES_FILE, {})
    proxies = user_proxies.get(str(user_id), {}).get("proxies", [])
    
    try:
        index = int(callback.data.split("_")[-1])
        proxy = proxies[index]
    except (IndexError, ValueError):
        await callback.answer("❌ Прокси не найден", show_alert=True)
        return
    
    tg_link = f"tg://proxy?server={proxy['server']}&port={proxy['port']}&secret={proxy['secret']}"
    
    text = (
        f"🔒 <b>{proxy['name']}</b>\n\n"
        f"🌐 <b>Сервер:</b> {proxy['server']}\n"
        f"🔌 <b>Порт:</b> {proxy['port']}\n"
        f"🔑 <b>Секрет:</b> <code>{proxy['secret']}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 <i>Нажми кнопку ниже для подключения!</i>"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_proxy_detail_keyboard(tg_link).as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "proxy_request")
async def proxy_request(callback: types.CallbackQuery, state: FSMContext):
    """Запрос нового прокси"""
    if not await require_private_chat(callback, "запрос прокси"):
        return
    
    await callback.answer()
    
    user = callback.from_user
    username = user.username or f"ID:{user.id}"
    
    # Отправляем админу
    request_msg = (
        f"🛰 <b>НОВЫЙ ЗАПРОС ПРОКСИ</b>\n\n"
        f"👤 @{username}\n"
        f"📱 ID: {user.id}\n\n"
        f"Ждёт персональный прокси-ключ!"
    )
    
    # ✅ Сохраняем запрос с msg_id и chat_id
    from handlers.proxy import proxy_pending_admin
    
    sent_count = 0
    first_msg_id = None
    first_chat_id = None
    
    for admin_id in ADMIN_IDS:
        try:
            msg = await callback.message.bot.send_message(
                admin_id,
                request_msg,
                reply_markup=get_admin_proxy_request_keyboard(user.id).as_markup(),
                parse_mode="HTML"
            )
            
            # Сохраняем данные первого сообщения
            if first_msg_id is None:
                first_msg_id = msg.message_id
                first_chat_id = msg.chat.id
            
            proxy_pending_admin[user.id] = {
                "username": username,
                "step": "waiting_for_admin",
                "msg_id": msg.message_id,
                "chat_id": msg.chat.id,
                "admin_id": admin_id
            }
            
            sent_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")
    
    # Показываем пользователю
    text = (
        "✅ <b>Запрос отправлен!</b>\n\n"
        f"Админ получил твою заявку.\n"
        f"Ожидай ответа...\n\n"
        f"💡 <i>Мы отправили запрос {sent_count} админу(ам)</i>"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_proxy_request_keyboard().as_markup(),
        parse_mode="HTML"
    )

# ==========================================
# FSM - ЗАПРОС VPN
# ==========================================

@router.message(ConfigRequest.waiting_for_device, F.text)
async def process_vpn_device(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Запрос отменён.", reply_markup=get_back_to_main_menu().as_markup())
        return
    
    device = message.text.strip()
    user = message.from_user
    username = user.username or f"ID:{user.id}"
    
    # Сохраняем запрос
    from handlers.vpn import pending_requests
    pending_requests[user.id] = {"device": device}
    
    # Отправляем админу
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