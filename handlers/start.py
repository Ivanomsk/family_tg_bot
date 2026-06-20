from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS, USER_PROXIES_FILE, VPN_DIR, BACKUP_DIR, ALLOWED_CHAT_ID
from utils.auto_delete import delete_user, delete_admin, delete_temp
from utils.logger import standard_logger, audit_logger
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
    get_help_keyboard,
    get_news_keyboard,
    get_problem_report_keyboard,
    get_problem_cancel_keyboard
)
from states.forms import ConfigRequest, ProxyRequest, NewsRequest, ProblemReport
import os
import re
import asyncio
from datetime import datetime

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
        return sorted([f for f in os.listdir(user_dir) if f.endswith('.vpn')])
    except Exception:
        return []


async def require_private_chat(callback: types.CallbackQuery, feature_name: str = "эта функция") -> bool:
    """Проверка, что callback в ЛС. Возвращает False если нужно прекратить."""
    if callback.message.chat.type != "private":
        bot_info = await callback.bot.get_me()
        bot_username = bot_info.username
        
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        builder = InlineKeyboardBuilder()
        builder.button(text="💬 Открыть чат с ботом", url=f"https://t.me/{bot_username}")
        builder.adjust(1)
        
        msg = await callback.message.answer(
            f"❌ <b>{feature_name.capitalize()} доступна только в личных сообщениях!</b>\n\n"
            f"👉 Нажмите кнопку ниже, чтобы перейти в ЛС:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
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


@router.message(Command("news"))
async def cmd_news(message: types.Message, state: FSMContext):
    """Команда /news — публикация новости (только админ)"""
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Эта команда доступна только администратору.")
        delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    
    await state.set_state(NewsRequest.waiting_for_text)
    
    text = (
        "📢 <b>ПУБЛИКАЦИЯ НОВОСТИ</b>\n\n"
        "Напишите текст новости, который будет отправлен в общий чат.\n\n"
        "Поддерживается HTML-разметка:\n"
        "<b>жирный</b>, <i>курсив</i>, <code>код</code>\n\n"
        "Или нажмите /cancel для отмены."
    )
    
    msg = await message.answer(
        text,
        reply_markup=get_problem_cancel_keyboard().as_markup(),
        parse_mode="HTML"
    )
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)


@router.message(Command("report"))
async def cmd_report(message: types.Message, state: FSMContext):
    """Команда /report — сообщить о проблеме"""
    await state.set_state(ProblemReport.waiting_for_text)
    
    text = (
        "📝 <b>СООБЩИТЬ О ПРОБЛЕМЕ</b>\n\n"
        "Опишите вашу проблему или предложение:\n\n"
        "Администратор получит ваше сообщение и ответит вам.\n\n"
        "Или нажмите /cancel для отмены."
    )
    
    msg = await message.answer(
        text,
        reply_markup=get_problem_cancel_keyboard().as_markup(),
        parse_mode="HTML"
    )
    delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)


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
    
    delete_temp(
        callback.message.bot, 
        callback.message.chat.id, 
        msg.message_id, 
        user_id=callback.from_user.id, 
        chat_type=callback.message.chat.type,
        allow_group=True
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
        "• Как подключить прокси\n"
        "• 📝 Сообщить о проблеме"
    )
    
    if is_admin:
        text += "\n\n" + "━" * 20 + "\n\n<b>⚙️ Админу:</b>\n" + "• Управление системой"
    
    builder = InlineKeyboardBuilder()
    builder.button(text="🔐 Как получить VPN", callback_data="help_vpn_info")
    builder.button(text="🛰 Как запросить прокси", callback_data="help_proxy_info")
    builder.button(text="👁 Как подключить прокси", callback_data="help_connect_info")
    builder.button(text="📝 Сообщить о проблеме", callback_data="problem_start")
    
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
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    
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
        "• Очистка старых\n\n"
        "📢 <b>Коммуникация:</b>\n"
        "• Опубликовать новость в чат"
    )
    
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="🔍 Проверка сроков", callback_data="admin_check_expiry")
    builder.button(text="📂 Конфиги пользователей", callback_data="admin_user_configs")
    builder.button(text="🛰 Управление прокси", callback_data="admin_proxy_manage")
    builder.button(text="📦 Создать бэкап", callback_data="admin_backup_create")
    builder.button(text="📋 Список бэкапов", callback_data="admin_backup_list")
    builder.button(text="📢 Опубликовать новость", callback_data="news_start")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(2, 2, 2, 1, 1)
    
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

@router.callback_query(F.data.startswith("vpn_req_auto_"))
async def vpn_req_auto_issue(callback: types.CallbackQuery):
    """Автоматическая генерация VPN конфига по запросу пользователя"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[-1])
    await callback.answer("⏳ Генерирую конфиг...")
    
    # ✅ ПОЛУЧАЕМ DEVICE NAME ИЗ ХРАНИЛИЩА
    from database.storage import load_json, save_json
    requests = load_json("bot_data/vpn_requests.json", {})
    request_data = requests.get(str(user_id), {})
    
    device = request_data.get("device", "device")  # iPhone, MacBook и т.д.
    username = request_data.get("username", f"user_{user_id}")
    
    # Очищаем username от @ и заменяем пробелы в device
    username = username.lstrip('@')
    device_safe = re.sub(r'[^\w\-]', '_', device)  # iPhone → iPhone, My Phone → My_Phone
    
    # Формируем имя файла: iPhone_20260620_120008.vpn
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    config_filename = f"{device_safe}_{timestamp}.vpn"
    
    await callback.message.edit_text(f"⏳ Генерирую VPN конфиг для {device}...")
    
    # Импортируем функцию генерации
    from utils.vpn_manager import issue_vpn_config
    
    # Генерируем конфиг (используем username для WireGuard - это техническое имя)
    result = issue_vpn_config(username, user_id=user_id)
    
    if 'error' in result:
        await callback.message.edit_text(f"❌ Ошибка генерации: {result['error']}")
        return
    
    # Сохраняем конфиг в папку пользователя
    user_dir = get_user_dir(username)
    config_path = os.path.join(user_dir, config_filename)
    
    with open(config_path, 'w') as f:
        f.write(result['config_string'])
    
    # ✅ ОТПРАВЛЯЕМ С ПРАВИЛЬНЫМ ИМЕНЕМ ФАЙЛА (.vpn)
    try:
        await callback.bot.send_document(
            chat_id=user_id,
            document=FSInputFile(config_path, filename=config_filename),  # iPhone_20260620_120008.vpn
            caption=(
                f"✅ <b>Ваш VPN конфиг готов!</b>\n\n"
                f"📱 Устройство: {device}\n"
                f"📍 IP: <code>{result['ip']}</code>\n"
                f"⏰ Срок: до {result['expires_at']}\n\n"
                f"💡 Импортируйте файл в Amnezia VPN"
            ),
            parse_mode="HTML"
        )
        
        await callback.message.edit_text(
            f"✅ <b>Конфиг выдан!</b>\n\n"
            f"👤 Пользователь: @{username}\n"
            f"📱 Устройство: {device}\n"
            f"📍 IP: {result['ip']}\n"
            f"⏰ Истекает: {result['expires_at']}\n\n"
            f"📁 Сохранён: <code>{config_filename}</code>",
            parse_mode="HTML"
        )
        
        # Логируем
        from utils.logger import audit_logger
        audit_logger.info(f"✅ VPN_ISSUED_AUTO | USER:{user_id} | DEVICE:{device} | IP:{result['ip']}")
        
        # ✅ УДАЛЯЕМ ЗАПРОС ИЗ ХРАНИЛИЩА
        del requests[str(user_id)]
        save_json("bot_data/vpn_requests.json", requests)
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка отправки пользователю: {e}")
        logger.error(f"Ошибка отправки конфига пользователю {user_id}: {e}")


@router.callback_query(F.data.startswith("vpn_req_reject_"))
async def vpn_req_reject(callback: types.CallbackQuery):
    """Отклонить запрос VPN"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[-1])
    
    try:
        await callback.bot.send_message(
            chat_id=user_id,
            text="❌ <b>Запрос VPN отклонён</b>\n\nОбратитесь к администратору для получения информации.",
            parse_mode="HTML"
        )
    except Exception:
        pass
    
    await callback.message.edit_text("❌ Запрос отклонён")
    await callback.answer()


# ==========================================
# ПРОКСИ - ВЫБОР
# ==========================================

@router.callback_query(F.data.startswith("proxy_select_"))
async def proxy_select(callback: types.CallbackQuery):
    """Выбор конкретного прокси"""
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
    
    from handlers.proxy import proxy_pending_admin
    proxy_pending_admin[user.id] = {
        "username": username,
        "step": "waiting_for_admin"
    }
    
    request_msg = (
        f"🛰 <b>НОВЫЙ ЗАПРОС ПРОКСИ</b>\n\n"
        f"👤 @{username}\n"
        f"📱 ID: {user.id}\n\n"
        f"Ждёт персональный прокси-ключ!"
    )
    
    sent_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await callback.message.bot.send_message(
                admin_id,
                request_msg,
                reply_markup=get_admin_proxy_request_keyboard(user.id).as_markup(),
                parse_mode="HTML"
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")
    
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
    
    # ✅ СОХРАНЯЕМ ЗАПРОС С DEVICE NAME
    from database.storage import load_json, save_json
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


# ==========================================
# НОВОСТИ (АДМИН)
# ==========================================

@router.callback_query(F.data == "news_start")
async def news_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало создания новости"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    
    await callback.answer()
    await state.set_state(NewsRequest.waiting_for_text)
    
    text = (
        "📢 <b>ПУБЛИКАЦИЯ НОВОСТИ</b>\n\n"
        "Напишите текст новости, который будет отправлен в общий чат.\n\n"
        "Поддерживается HTML-разметка:\n"
        "<b>жирный</b>, <i>курсив</i>, <code>код</code>\n\n"
        "Или нажмите /cancel для отмены."
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_problem_cancel_keyboard().as_markup(),
        parse_mode="HTML"
    )


@router.message(NewsRequest.waiting_for_text, F.text)
async def news_get_text(message: types.Message, state: FSMContext):
    """Получение текста новости и показ превью"""
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Публикация отменена.", reply_markup=get_back_to_main_menu().as_markup())
        return
    
    news_text = message.text.strip()
    
    # Сохраняем текст во временном хранилище
    temp_news = load_json("bot_data/temp_news.json", {})
    temp_news[str(message.from_user.id)] = news_text
    save_json("bot_data/temp_news.json", temp_news)
    
    # Показываем превью с кнопками подтверждения
    text = (
        "📢 <b>ПРЕВЬЮ НОВОСТИ</b>\n\n"
        f"{news_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Отправить в общий чат?"
    )
    
    await message.answer(
        text,
        reply_markup=get_news_keyboard().as_markup(),
        parse_mode="HTML"
    )
    
    await state.clear()


@router.callback_query(F.data == "news_confirm")
async def news_confirm(callback: types.CallbackQuery):
    """Подтверждение и отправка новости"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    
    await callback.answer()
    
    temp_news = load_json("bot_data/temp_news.json", {})
    news_text = temp_news.get(str(callback.from_user.id))
    
    if not news_text:
        await callback.message.answer("❌ Текст новости не найден. Начните заново.")
        return
    
    if not ALLOWED_CHAT_ID:
        await callback.message.answer("❌ ALLOWED_CHAT_ID не настроен в .env")
        return
    
    try:
        msg = await callback.message.bot.send_message(
            ALLOWED_CHAT_ID,
            news_text,
            parse_mode="HTML"
        )
        
        # ✅ ЛОГИРОВАНИЕ ПУБЛИКАЦИИ НОВОСТИ
        logger.info(
            f"📢 НОВОСТЬ ОПУБЛИКОВАНА | "
            f"Админ: {callback.from_user.id} | "
            f"Чат: {ALLOWED_CHAT_ID} | "
            f"MessageID: {msg.message_id} | "
            f"Текст: {news_text[:100]}{'...' if len(news_text) > 100 else ''}"
        )
        
        # ✅ AUDIT-ЛОГ
        audit_logger.info(
            f"ACTION:NEWS_PUBLISH | "
            f"ADMIN:{callback.from_user.id} | "
            f"CHAT:{ALLOWED_CHAT_ID} | "
            f"MSG_ID:{msg.message_id} | "
            f"TEXT:{news_text[:80]}"
        )
        
        await callback.message.answer(
            f"✅ <b>Новость опубликована!</b>\n\n"
            f"Сообщение ID: {msg.message_id}\n"
            f"Чат: {ALLOWED_CHAT_ID}",
            parse_mode="HTML"
        )
        
        # Удаляем временный текст
        del temp_news[str(callback.from_user.id)]
        save_json("bot_data/temp_news.json", temp_news)
        
    except Exception as e:
        logger.error(f"❌ Ошибка публикации новости: {e}")
        audit_logger.error(f"ACTION:NEWS_PUBLISH_FAILED | ADMIN:{callback.from_user.id} | ERROR:{e}")
        await callback.message.answer(f"❌ Ошибка отправки: {e}")


@router.callback_query(F.data == "news_cancel")
async def news_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Отмена публикации новости"""
    await callback.answer()
    await state.clear()
    
    temp_news = load_json("bot_data/temp_news.json", {})
    if str(callback.from_user.id) in temp_news:
        del temp_news[str(callback.from_user.id)]
        save_json("bot_data/temp_news.json", temp_news)
    
    await callback.message.answer(
        "❌ Публикация отменена.",
        reply_markup=get_back_to_main_menu().as_markup()
    )


# ==========================================
# СООБЩИТЬ О ПРОБЛЕМЕ (ПОЛЬЗОВАТЕЛЬ)
# ==========================================

@router.callback_query(F.data == "problem_start")
async def problem_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало репорта о проблеме"""
    await callback.answer()
    await state.set_state(ProblemReport.waiting_for_text)
    
    text = (
        "📝 <b>СООБЩИТЬ О ПРОБЛЕМЕ</b>\n\n"
        "Опишите вашу проблему или предложение:\n\n"
        "Администратор получит ваше сообщение и ответит вам.\n\n"
        "Или нажмите /cancel для отмены."
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_problem_cancel_keyboard().as_markup(),
        parse_mode="HTML"
    )


@router.message(ProblemReport.waiting_for_text, F.text)
async def problem_get_text(message: types.Message, state: FSMContext):
    """Получение текста проблемы и отправка админу"""
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Отправка отменена.", reply_markup=get_back_to_main_menu().as_markup())
        return
    
    problem_text = message.text.strip()
    user = message.from_user
    username = user.username or f"ID:{user.id}"
    
    # ✅ ЛОГИРОВАНИЕ СООБЩЕНИЯ О ПРОБЛЕМЕ
    logger.info(
        f"📝 СООБЩЕНИЕ О ПРОБЛЕМЕ | "
        f"От: @{username} (ID: {user.id}) | "
        f"Текст: {problem_text[:100]}{'...' if len(problem_text) > 100 else ''}"
    )
    
    # ✅ AUDIT-ЛОГ
    audit_logger.info(
        f"ACTION:PROBLEM_REPORT | "
        f"USER:{user.id} | "
        f"USERNAME:{username} | "
        f"TEXT:{problem_text[:80]}"
    )
    
    admin_msg = (
        f"📝 <b>НОВОЕ СООБЩЕНИЕ О ПРОБЛЕМЕ</b>\n\n"
        f"👤 <b>От:</b> @{username}\n"
        f"📱 <b>ID:</b> {user.id}\n"
        f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{problem_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 <i>Чтобы ответить — сделайте Reply на это сообщение и напишите текст</i>\n"
        f"💡 <i>Или используйте: /reply {user.id} ваш ответ</i>"
    )
    
    sent_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                admin_msg,
                parse_mode="HTML"
            )
            sent_count += 1
            logger.debug(f"Отправлено уведомление админу {admin_id} о проблеме от {user.id}")
        except Exception as e:
            logger.error(f"Ошибка отправки репорта админу {admin_id}: {e}")
            audit_logger.error(f"ACTION:PROBLEM_REPORT_SEND_FAILED | ADMIN:{admin_id} | USER:{user.id} | ERROR:{e}")
    
    await message.answer(
        f"✅ <b>Сообщение отправлено!</b>\n\n"
        f"Администратор получил ваш запрос.\n"
        f"Мы ответим вам в личных сообщениях.\n\n"
        f"💡 <i>Отправлено {sent_count} админу(ам)</i>",
        reply_markup=get_back_to_main_menu().as_markup(),
        parse_mode="HTML"
    )
    
    await state.clear()


@router.callback_query(F.data == "problem_cancel")
async def problem_cancel(callback: types.CallbackQuery, state: FSMContext):
    """Отмена репорта"""
    await callback.answer()
    await state.clear()
    
    await callback.message.answer(
        "❌ Отправка отменена.",
        reply_markup=get_back_to_main_menu().as_markup()
    )


# ==========================================
# ОТВЕТ АДМИНА ПОЛЬЗОВАТЕЛЮ
# ==========================================

@router.message(F.reply_to_message & F.from_user.id.in_(ADMIN_IDS))
async def admin_reply_to_user(message: types.Message):
    """Админ отвечает пользователю через Reply на сообщение о проблеме"""
    reply_msg = message.reply_to_message
    
    if not reply_msg or not reply_msg.text or "НОВОЕ СООБЩЕНИЕ О ПРОБЛЕМЕ" not in reply_msg.text:
        return
    
    import re
    match = re.search(r'ID:\s*(\d+)', reply_msg.text)
    if not match:
        await message.answer("❌ Не удалось определить ID пользователя")
        return
    
    user_id = int(match.group(1))
    answer_text = message.text.strip()
    
    try:
        await message.bot.send_message(
            user_id,
            f"💬 <b>Ответ администратора:</b>\n\n"
            f"{answer_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💡 <i>Если вопрос решён — напишите нам ещё!</i>",
            parse_mode="HTML"
        )
        
        # ✅ ЛОГИРОВАНИЕ ОТВЕТА АДМИНА
        logger.info(
            f"💬 ОТВЕТ АДМИНА (Reply) | "
            f"Админ: {message.from_user.id} → "
            f"Пользователь: {user_id} | "
            f"Текст: {answer_text[:100]}{'...' if len(answer_text) > 100 else ''}"
        )
        
        # ✅ AUDIT-ЛОГ
        audit_logger.info(
            f"ACTION:ADMIN_REPLY | "
            f"ADMIN:{message.from_user.id} | "
            f"TO_USER:{user_id} | "
            f"METHOD:REPLY | "
            f"TEXT:{answer_text[:80]}"
        )
        
        await message.answer(
            f"✅ <b>Ответ отправлен пользователю!</b>\n\n"
            f"👤 ID: {user_id}\n"
            f"📝 Текст: {answer_text[:50]}{'...' if len(answer_text) > 50 else ''}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки ответа пользователю {user_id}: {e}")
        audit_logger.error(f"ACTION:ADMIN_REPLY_FAILED | ADMIN:{message.from_user.id} | USER:{user_id} | ERROR:{e}")
        await message.answer(f"❌ Ошибка отправки: {e}\n\nВозможно, пользователь не запускал бота.")


@router.message(Command("reply"))
async def cmd_reply(message: types.Message):
    """Команда /reply user_id текст — ответ пользователю"""
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Эта команда доступна только администратору.")
        delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Используйте: <code>/reply user_id текст</code>\n\n"
            "Пример: <code>/reply 6538784737 Здравствуйте! Проблема решена.</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID пользователя. ID должен быть числом.")
        return
    
    answer_text = parts[2].strip()
    
    try:
        await message.bot.send_message(
            user_id,
            f"💬 <b>Ответ администратора:</b>\n\n"
            f"{answer_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💡 <i>Если вопрос решён — напишите нам ещё!</i>",
            parse_mode="HTML"
        )
        
        # ✅ ЛОГИРОВАНИЕ ОТВЕТА ЧЕРЕЗ /reply
        logger.info(
            f"💬 ОТВЕТ ЧЕРЕЗ /reply | "
            f"Админ: {message.from_user.id} → "
            f"Пользователь: {user_id} | "
            f"Текст: {answer_text[:100]}{'...' if len(answer_text) > 100 else ''}"
        )
        
        # ✅ AUDIT-ЛОГ
        audit_logger.info(
            f"ACTION:ADMIN_REPLY | "
            f"ADMIN:{message.from_user.id} | "
            f"TO_USER:{user_id} | "
            f"METHOD:COMMAND | "
            f"TEXT:{answer_text[:80]}"
        )
        
        await message.answer(
            f"✅ <b>Ответ отправлен!</b>\n\n"
            f"👤 Пользователь ID: {user_id}\n"
            f"📝 Текст: {answer_text[:50]}{'...' if len(answer_text) > 50 else ''}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Ошибка отправки ответа пользователю {user_id} через /reply: {e}")
        audit_logger.error(f"ACTION:ADMIN_REPLY_FAILED | ADMIN:{message.from_user.id} | USER:{user_id} | ERROR:{e}")
        await message.answer(f"❌ Ошибка отправки: {e}\n\nВозможно, пользователь не запускал бота.")


# ==========================================
# ОБЩАЯ КНОПКА ОТМЕНЫ
# ==========================================

@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: types.CallbackQuery, state: FSMContext):
    """Универсальная кнопка отмены"""
    await callback.answer()
    await state.clear()
    
    await callback.message.answer(
        "❌ Действие отменено.",
        reply_markup=get_back_to_main_menu().as_markup()
    )