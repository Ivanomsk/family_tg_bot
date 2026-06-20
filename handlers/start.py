from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS, USER_PROXIES_FILE, VPN_DIR, BACKUP_DIR, ALLOWED_CHAT_ID
from utils.auto_delete import delete_user, delete_admin, delete_temp
from utils.logger import standard_logger, audit_logger
from utils.stats import update_stats
from utils.expiry import get_vpn_config_age, get_proxy_age
from database.storage import load_json, save_json
from utils.vpn_manager import VPN_USERS_FILE, load_vpn_db
from keyboards.inline import (
    get_main_menu_keyboard,
    get_back_to_main_menu,
    get_vpn_main_keyboard,
    get_vpn_list_keyboard,
    get_vpn_empty_keyboard,
    get_vpn_request_keyboard,
    get_admin_vpn_request_keyboard,
    get_proxy_main_keyboard,
    get_proxy_list_keyboard,
    get_proxy_empty_keyboard,
    get_proxy_detail_keyboard,
    get_proxy_request_keyboard,
    get_admin_proxy_request_keyboard,
    get_help_main_keyboard,
    get_admin_main_keyboard,
    get_admin_users_keyboard,
    get_back_keyboard,
    get_news_keyboard,
    get_amnezia_announce_keyboard,
    get_problem_cancel_keyboard
)
from states.forms import ConfigRequest, ProxyRequest, NewsRequest, ProblemReport, ProxyIssue
import os
import re
import asyncio
import urllib.parse
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


async def require_private_chat(callback: types.CallbackQuery, feature_name: str = "эта функция") -> bool:
    if callback.message.chat.type != "private":
        bot_info = await callback.bot.get_me()
        bot_username = bot_info.username
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
# НАВИГАЦИЯ ПО МЕНЮ
# ==========================================

@router.callback_query(F.data == "menu_main")
async def menu_main(callback: types.CallbackQuery):
    await callback.answer()
    is_admin = callback.from_user.id in ADMIN_IDS
    await callback.message.edit_text(
        "👋 <b>Главное меню</b>\n\nВыбери раздел:",
        reply_markup=get_main_menu_keyboard(is_admin).as_markup(),
        parse_mode="HTML"
    )


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


@router.callback_query(F.data == "menu_proxy_main")
async def menu_proxy_main(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🛰 <b>Управление прокси</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_proxy_main_keyboard().as_markup()
    )


@router.callback_query(F.data == "menu_ping")
async def menu_ping(callback: types.CallbackQuery):
    await callback.answer()
    msg = await callback.message.answer(
        "🏓 <b>Pong!</b>\n\n✅ Бот работает стабильно\n⚡ Время отклика: мгновенно",
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


@router.callback_query(F.data == "menu_help")
async def menu_help(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "📖 <b>Справочник</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=get_help_main_keyboard().as_markup()
    )


# ==========================================
# ПОМОЩЬ - ИНСТРУКЦИИ
# ==========================================

@router.callback_query(F.data == "help_vpn_how")
async def help_vpn_how(callback: types.CallbackQuery):
    text = (
        "📖 <b>Как получить VPN</b>\n\n"
        "1️⃣ Нажмите кнопку <b>«VPN»</b> в главном меню\n"
        "2️⃣ Нажмите <b>«Запросить новый»</b>\n"
        "3️⃣ Администратор одобрит заявку, и вы получите конфиг\n"
        "4️⃣ Скачайте файл и импортируйте его в клиент Amnezia VPN\n\n"
        "📌 <b>Важно:</b> конфиг действует 30 дней."
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_help").as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "help_proxy_how")
async def help_proxy_how(callback: types.CallbackQuery):
    text = (
        "📖 <b>Как запросить прокси</b>\n\n"
        "1️⃣ Нажмите кнопку <b>«Прокси»</b> в главном меню\n"
        "2️⃣ Нажмите <b>«Запросить новый»</b>\n"
        "3️⃣ Администратор выпишет ключ, и он появится в списке\n"
        "4️⃣ Нажмите на прокси, чтобы увидеть данные для подключения\n\n"
        "📌 <b>Важно:</b> прокси действует 30 дней."
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_help").as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "help_proxy_connect")
async def help_proxy_connect(callback: types.CallbackQuery):
    text = (
        "📖 <b>Как подключить прокси</b>\n\n"
        "1️⃣ Нажмите <b>«Прокси»</b> в главном меню\n"
        "2️⃣ Выберите нужный прокси из списка\n"
        "3️⃣ Нажмите кнопку <b>«Подключить в Telegram»</b>\n"
        "4️⃣ Telegram автоматически откроет настройки и подключит прокси\n\n"
        "📌 <b>Важно:</b> прокси работает только в Telegram."
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_help").as_markup()
    )
    await callback.answer()


# ==========================================
# АДМИН-ПАНЕЛЬ
# ==========================================

@router.callback_query(F.data == "menu_admin_main")
async def menu_admin_main(callback: types.CallbackQuery):
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


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        "👥 <b>Управление пользователями</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_admin_users_keyboard().as_markup()
    )


@router.callback_query(F.data == "admin_check_expiry")
async def admin_check_expiry(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    from utils.expiry import check_all_vpn_expiry, check_all_proxy_expiry
    vpn_expired, vpn_expiring = check_all_vpn_expiry()
    proxy_expired, proxy_expiring = check_all_proxy_expiry()
    
    text = "🔍 <b>Проверка сроков</b>\n\n"
    if vpn_expired or vpn_expiring or proxy_expired or proxy_expiring:
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
    else:
        text += "✅ Все VPN и прокси активны"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_admin_main").as_markup()
    )
    await callback.answer()


# ==========================================
# НОВОСТИ
# ==========================================

@router.callback_query(F.data == "news_start")
async def news_start(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        "📢 <b>Публикация новости</b>\n\nВыберите тип новости:",
        parse_mode="HTML",
        reply_markup=get_news_keyboard().as_markup()
    )


@router.callback_query(F.data == "news_type_regular")
async def news_type_regular(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        "📰 <b>Обычная новость</b>\n\n"
        "Отправьте текст новости.\n"
        "Поддерживается HTML-разметка.\n\n"
        "Пример:\n"
        "<code>&lt;b&gt;Важная новость!&lt;/b&gt;\n"
        "Текст новости с &lt;a href=&quot;https://example.com&quot;&gt;ссылкой&lt;/a&gt;.</code>\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "news_type_amnezia")
async def news_type_amnezia(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    text = (
        "<b>📢 Обновление Amnezia VPN</b>\n\n"
        "Доступна новая версия клиента для всех платформ.\n\n"
        "<b>Для ПК:</b>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN_x64.exe'>Windows</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN.dmg'>macOS (Intel)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN-arm64.dmg'>macOS (Apple Silicon)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN_Linux.deb'>Linux</a>\n\n"
        "<b>Для мобильных:</b>\n"
        "• <a href='https://play.google.com/store/apps/details?id=org.amnezia.vpn'>Android (Google Play)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN.apk'>Android (APK с GitHub)</a>\n"
        "• <a href='https://apps.apple.com/app/amneziavpn/id1600529900'>iOS (App Store)</a>\n\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest'>Все версии на GitHub</a>\n\n"
        "<b>Важно:</b> если вы меняете источник установки, может возникнуть ошибка."
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_amnezia_announce_keyboard().as_markup(),
        disable_web_page_preview=False
    )
    await callback.answer()


@router.callback_query(F.data == "amnezia_publish")
async def amnezia_publish(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    text = (
        "<b>📢 Обновление Amnezia VPN</b>\n\n"
        "Доступна новая версия клиента для всех платформ.\n\n"
        "<b>Для ПК:</b>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN_x64.exe'>Windows</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN.dmg'>macOS (Intel)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN-arm64.dmg'>macOS (Apple Silicon)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN_Linux.deb'>Linux</a>\n\n"
        "<b>Для мобильных:</b>\n"
        "• <a href='https://play.google.com/store/apps/details?id=org.amnezia.vpn'>Android (Google Play)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN.apk'>Android (APK с GitHub)</a>\n"
        "• <a href='https://apps.apple.com/app/amneziavpn/id1600529900'>iOS (App Store)</a>\n\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest'>Все версии на GitHub</a>\n\n"
        "<b>Важно:</b> если вы меняете источник установки, может возникнуть ошибка."
    )
    
    try:
        await callback.bot.send_message(
            ALLOWED_CHAT_ID,
            text,
            parse_mode="HTML",
            disable_web_page_preview=False
        )
        await callback.answer("✅ Анонс опубликован в чате!", show_alert=True)
        await callback.message.edit_text(
            "⚙️ <b>Админ-панель</b>\n\nАнонс успешно опубликован!",
            parse_mode="HTML",
            reply_markup=get_admin_main_keyboard().as_markup()
        )
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


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
# СООБЩИТЬ О ПРОБЛЕМЕ
# ==========================================

@router.callback_query(F.data == "problem_start")
async def problem_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(ProblemReport.waiting_for_text)
    await callback.message.edit_text(
        "📝 <b>СООБЩИТЬ О ПРОБЛЕМЕ</b>\n\n"
        "Опишите вашу проблему или предложение:\n\n"
        "Администратор получит ваше сообщение и ответит вам.\n\n"
        "Или нажмите /cancel для отмены.",
        reply_markup=get_problem_cancel_keyboard().as_markup(),
        parse_mode="HTML"
    )


@router.message(ProblemReport.waiting_for_text, F.text)
async def problem_get_text(message: types.Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Отправка отменена.", reply_markup=get_back_to_main_menu().as_markup())
        return
    
    problem_text = message.text.strip()
    user = message.from_user
    username = user.username or f"ID:{user.id}"
    
    admin_msg = (
        f"📝 <b>НОВОЕ СООБЩЕНИЕ О ПРОБЛЕМЕ</b>\n\n"
        f"👤 <b>От:</b> @{username}\n"
        f"📱 <b>ID:</b> {user.id}\n"
        f"🕐 <b>Время:</b> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{problem_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💡 <i>Чтобы ответить — сделайте Reply на это сообщение</i>"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, admin_msg, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")
    
    await message.answer(
        "✅ <b>Сообщение отправлено!</b>\n\nАдминистратор получил ваш запрос.",
        reply_markup=get_back_to_main_menu().as_markup(),
        parse_mode="HTML"
    )
    await state.clear()


@router.callback_query(F.data == "problem_cancel")
async def problem_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.answer("❌ Отправка отменена.", reply_markup=get_back_to_main_menu().as_markup())


@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.answer("❌ Действие отменено.", reply_markup=get_back_to_main_menu().as_markup())


# ==========================================
# ОТВЕТ АДМИНА ПОЛЬЗОВАТЕЛЮ (REPLY)
# ==========================================

@router.message(F.reply_to_message & F.from_user.id.in_(ADMIN_IDS))
async def admin_reply_to_user(message: types.Message):
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
            f"💬 <b>Ответ администратора:</b>\n\n{answer_text}",
            parse_mode="HTML"
        )
        await message.answer(f"✅ <b>Ответ отправлен!</b>\n👤 ID: {user_id}", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


# ==========================================
# ОТВЕТ АДМИНА ПО КОМАНДЕ /reply
# ==========================================

@router.message(Command("reply"))
async def cmd_reply(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Только для администратора.")
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "❌ Используйте: <code>/reply user_id текст</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID.")
        return
    
    answer_text = parts[2].strip()
    
    try:
        await message.bot.send_message(
            user_id,
            f"💬 <b>Ответ администратора:</b>\n\n{answer_text}",
            parse_mode="HTML"
        )
        await message.answer(f"✅ <b>Ответ отправлен!</b>\n👤 ID: {user_id}", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ==========================================
# АВТОМАТИЧЕСКАЯ ВЫДАЧА VPN (АДМИН)
# ==========================================

@router.callback_query(F.data.startswith("vpn_req_auto_"))
async def vpn_req_auto_issue(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[-1])
    await callback.answer("⏳ Генерирую конфиг...")
    
    from database.storage import load_json, save_json
    requests = load_json("bot_data/vpn_requests.json", {})
    request_data = requests.get(str(user_id), {})
    
    if not request_data:
        await callback.message.edit_text("❌ Запрос не найден.")
        return
    
    device = request_data.get("device", "device")
    username = request_data.get("username", f"user_{user_id}")
    username = username.lstrip('@')
    device_safe = re.sub(r'[^\w\-]', '_', device)
    
    now = datetime.now()
    date_str = now.strftime('%d.%m')
    config_filename = f"{device_safe}_{date_str}.vpn"
    
    await callback.message.edit_text(f"⏳ Генерирую VPN конфиг для {device}...")
    
    from utils.vpn_manager import issue_vpn_config
    result = issue_vpn_config(username, user_id=user_id)
    
    if 'error' in result:
        await callback.message.edit_text(f"❌ Ошибка: {result['error']}")
        return
    
    user_dir = get_user_dir(username)
    config_path = os.path.join(user_dir, config_filename)
    counter = 1
    while os.path.exists(config_path):
        base, ext = os.path.splitext(config_filename)
        config_filename = f"{base}_{counter}{ext}"
        config_path = os.path.join(user_dir, config_filename)
        counter += 1
    
    with open(config_path, 'w') as f:
        f.write(result['config_string'])
    
    expires_display = result['expires_at']
    
    try:
        await callback.bot.send_document(
            chat_id=user_id,
            document=FSInputFile(config_path, filename=config_filename),
            caption=(
                f"✅ <b>Ваш VPN конфиг готов!</b>\n\n"
                f"📱 Устройство: {device}\n"
                f"⏰ Срок: до {expires_display}"
            ),
            parse_mode="HTML"
        )
        
        await callback.message.edit_text(
            f"✅ <b>Конфиг выдан!</b>\n\n"
            f"👤 Пользователь: @{username}\n"
            f"📱 Устройство: {device}\n"
            f"⏰ Истекает: {expires_display}\n"
            f"📁 Сохранён: <code>{config_filename}</code>",
            parse_mode="HTML"
        )
        
        if str(user_id) in requests:
            del requests[str(user_id)]
            save_json("bot_data/vpn_requests.json", requests)
        
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка: {e}")

# ==========================================
# VPN - ВЫБОР КОНФИГА (КАРТОЧКА)
# ==========================================

@router.callback_query(F.data.startswith("vpn_select_"))
async def vpn_select(callback: types.CallbackQuery):
    """Выбор конкретного VPN конфига — показываем карточку с данными"""
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
    
    # Ищем данные конфига в vpn_users.json
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
    
    # Формируем карточку
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
        
        # Определяем статус
        if is_permanent:
            status = "♾️ Бессрочный"
        elif is_expired or not active:
            status = "🔴 Истек / Неактивен"
        elif days_left is not None and days_left <= 3:
            status = f"🟡 Истекает через {days_left} дн."
        else:
            status = "🟢 Активен"
        
        # Формируем текст
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
        
        # Добавляем сообщение для просроченного
        if is_expired and not is_permanent:
            text += "\n\n🔴 <b>Конфиг просрочен!</b>\nСкачивание недоступно. Запросите продление."
        
        buttons = []
        
        # Кнопка "Скачать" — только если активен и не истек или бессрочный
        if is_permanent or (not is_expired and active):
            buttons.append([InlineKeyboardButton(
                text="📥 Скачать конфиг",
                callback_data=f"dwn_{user_id}_{config_index}"
            )])
        
        # Кнопка "Запросить продление" — только если НЕ бессрочный
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
        # Если конфиг не найден в базе, но файл существует — показываем базовую карточку
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
    """Скачать VPN конфиг (только если не истек)"""
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
    
    # ✅ ПРОВЕРКА: конфиг не должен быть истекшим (бессрочные пропускаем)
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
# ПРОКСИ - ПОКАЗ СПИСКА
# ==========================================

@router.callback_query(F.data == "menu_proxy")
async def menu_proxy(callback: types.CallbackQuery):
    """Показать список прокси пользователя"""
    if not await require_private_chat(callback, "просмотр прокси"):
        return
    
    await callback.answer()
    
    user_id = callback.from_user.id
    user_proxies = load_json(USER_PROXIES_FILE, {})
    proxies = user_proxies.get(str(user_id), {}).get("proxies", [])
    
    if not proxies:
        text = "🛰 <b>Мои прокси</b>\n\n"
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


@router.callback_query(F.data.startswith("proxy_select_"))
async def proxy_select(callback: types.CallbackQuery):
    """Выбор конкретного прокси"""
    if not await require_private_chat(callback, "просмотр прокси"):
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
    
    # Получаем username пользователя
    username = callback.from_user.username or f"ID:{user_id}"
    
    # Формируем ссылку для подключения
    tg_link = f"tg://proxy?server={proxy['server']}&port={proxy['port']}&secret={proxy['secret']}"
    
    # Форматируем дату выдачи
    issued_at_raw = proxy.get('issued_at', 'не указана')
    if issued_at_raw != 'не указана':
        try:
            issued_dt = datetime.fromisoformat(issued_at_raw)
            issued_at = issued_dt.strftime('%d.%m.%Y %H:%M')
        except:
            issued_at = issued_at_raw
    else:
        issued_at = 'не указана'
    
    # Проверяем бессрочный статус
    is_permanent = proxy.get('permanent', False)
    
    # Проверяем срок действия
    expires_at = None
    days_left = None
    is_expired = False
    
    if not is_permanent and issued_at_raw != 'не указана':
        try:
            issued_date = datetime.fromisoformat(issued_at_raw)
            expires_date = issued_date + timedelta(days=30)
            expires_at = expires_date.strftime('%d.%m.%Y')
            days_left = (expires_date - datetime.now()).days
            if days_left < 0:
                is_expired = True
        except:
            pass
    
    # Определяем статус
    if is_permanent:
        status = "♾️ Бессрочный"
    elif is_expired:
        status = "🔴 Истек"
    elif days_left is not None and days_left <= 3:
        status = f"🟡 Истекает через {days_left} дн."
    else:
        status = "🟢 Активен"
    
    text = (
        f"🔒 <b>Карточка прокси</b>\n\n"
        f"👤 <b>Пользователь:</b> @{username}\n"
        f"📁 <b>Имя:</b> {proxy['name']}\n"
        f"🌐 <b>Сервер:</b> {proxy['server']}\n"
        f"🔌 <b>Порт:</b> {proxy['port']}\n"
        f"📅 <b>Выдан:</b> {issued_at}\n"
        f"📅 <b>Истекает:</b> {expires_at if expires_at else ('♾️ Бессрочный' if is_permanent else 'не указана')}\n"
        f"📊 <b>Статус:</b> {status}\n"
    )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    buttons = []
    
    # Кнопка подключения только если не истек
    if not is_expired and not is_permanent:
        buttons.append([InlineKeyboardButton(
            text="📱 Подключить в Telegram",
            url=tg_link
        )])
    elif is_permanent:
        buttons.append([InlineKeyboardButton(
            text="📱 Подключить в Telegram",
            url=tg_link
        )])
    
    # Кнопка продления — если не бессрочный и (истек или осталось ≤ 5 дней)
    if not is_permanent:
        if is_expired or (days_left is not None and days_left <= 5):
            buttons.append([InlineKeyboardButton(
                text="🔄 Запросить продление",
                callback_data=f"proxy_extend_{user_id}_{index}"
            )])
    
    buttons.append([InlineKeyboardButton(
        text="🔙 К списку",
        callback_data="menu_proxy"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "proxy_request")
async def proxy_request(callback: types.CallbackQuery):
    """Запрос нового прокси"""
    if not await require_private_chat(callback, "запрос прокси"):
        return
    
    await callback.answer()
    
    user = callback.from_user
    username = user.username or f"ID:{user.id}"
    
    # Отправляем запрос админу
    request_msg = (
        f"🛰 <b>НОВЫЙ ЗАПРОС ПРОКСИ</b>\n\n"
        f"👤 @{username}\n"
        f"📱 ID: {user.id}\n\n"
        f"Ждёт персональный прокси-ключ!"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📝 Выписать ключ",
                callback_data=f"proxy_issue_{user.id}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"proxy_reject_{user.id}"
            )
        ]
    ])
    
    sent_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                request_msg,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            sent_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки админу {admin_id}: {e}")
    
    text = (
        "✅ <b>Запрос отправлен!</b>\n\n"
        f"Админ получил твою заявку.\n"
        f"Ожидай ответа...\n\n"
        f"💡 <i>Отправлено {sent_count} админу(ам)</i>"
    )
    
    await callback.message.edit_text(
        text,
        reply_markup=get_proxy_request_keyboard().as_markup(),
        parse_mode="HTML"
    )


# ==========================================
# ПРОКСИ - АДМИН (ВЫДАЧА/ОТКЛОНЕНИЕ)
# ==========================================

@router.callback_query(F.data.startswith("proxy_issue_"))
async def proxy_issue(callback: types.CallbackQuery, state: FSMContext):
    """Админ начинает выдачу прокси — запрашиваем имя"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[-1])
    
    # Сохраняем user_id в состоянии
    await state.update_data(target_user_id=user_id)
    await state.set_state(ProxyIssue.waiting_for_name)
    
    await callback.message.edit_text(
        "📝 <b>Введите название прокси</b>\n\n"
        "Например: Основной, Резерв, Для работы и т.д.\n\n"
        "Или нажмите /cancel для отмены.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ProxyIssue.waiting_for_name, F.text)
async def proxy_issue_get_name(message: types.Message, state: FSMContext):
    """Получаем имя прокси, запрашиваем ключ"""
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_back_to_main_menu().as_markup())
        return
    
    name = message.text.strip()
    await state.update_data(proxy_name=name)
    await state.set_state(ProxyIssue.waiting_for_key)
    
    await message.answer(
        "🔑 <b>Введите ключ прокси</b>\n\n"
        "Вставьте ссылку в формате:\n"
        "<code>tg://proxy?server=nas-msk.online&port=443&secret=eec03592318ff9f161f29538302627ebfd6e61732d6d736b2e6f6e6c696e65</code>\n\n"
        "Или нажмите /cancel для отмены.",
        parse_mode="HTML"
    )


@router.message(ProxyIssue.waiting_for_key, F.text)
async def proxy_issue_get_key(message: types.Message, state: FSMContext):
    """Получаем ключ и сохраняем прокси"""
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_back_to_main_menu().as_markup())
        return
    
    key_text = message.text.strip()
    
    # Проверяем формат tg://proxy
    if not key_text.startswith('tg://proxy'):
        await message.answer(
            "❌ <b>Неверный формат!</b>\n\n"
            "Ссылка должна начинаться с <code>tg://proxy</code>\n\n"
            "Пример:\n"
            "<code>tg://proxy?server=nas-msk.online&port=443&secret=eec03592318ff9f161f29538302627ebfd6e61732d6d736b2e6f6e6c696e65</code>",
            parse_mode="HTML"
        )
        return
    
    # Парсим параметры
    parsed = urllib.parse.urlparse(key_text)
    params = urllib.parse.parse_qs(parsed.query)
    
    server = params.get('server', [None])[0]
    port = params.get('port', [None])[0]
    secret = params.get('secret', [None])[0]
    
    if not server or not port or not secret:
        await message.answer(
            "❌ <b>Не хватает параметров!</b>\n\n"
            "Должны быть: <code>server</code>, <code>port</code>, <code>secret</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        port = int(port)
    except ValueError:
        await message.answer("❌ Порт должен быть числом.")
        return
    
    # Получаем данные из состояния
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    proxy_name = data.get('proxy_name', 'Прокси')
    
    # Сохраняем прокси
    user_proxies = load_json(USER_PROXIES_FILE, {})
    user_id_str = str(target_user_id)
    
    if user_id_str not in user_proxies:
        user_proxies[user_id_str] = {"proxies": []}
    
    proxy_data = {
        "name": proxy_name,
        "server": server,
        "port": port,
        "secret": secret,
        "issued_at": datetime.now().isoformat(),
        "issued_by": message.from_user.id
    }
    
    user_proxies[user_id_str]["proxies"].append(proxy_data)
    save_json(USER_PROXIES_FILE, user_proxies)
    
    # Отправляем пользователю
    tg_link = f"tg://proxy?server={server}&port={port}&secret={secret}"
    
    try:
        await message.bot.send_message(
            target_user_id,
            f"✅ <b>Ваш персональный прокси готов!</b>\n\n"
            f"📁 <b>Имя:</b> {proxy_name}\n"
            f"🌐 <b>Сервер:</b> {server}\n"
            f"🔌 <b>Порт:</b> {port}\n"
            f"📅 <b>Выдан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"💡 Нажмите кнопку для подключения:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 Подключить в Telegram", url=tg_link)]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки прокси пользователю {target_user_id}: {e}")
        await message.answer(f"❌ Ошибка отправки пользователю: {e}")
        await state.clear()
        return
    
    await message.answer(
        f"✅ <b>Прокси выдан!</b>\n\n"
        f"👤 Пользователь: ID {target_user_id}\n"
        f"📁 Имя: {proxy_name}\n"
        f"🌐 Сервер: {server}\n"
        f"🔌 Порт: {port}\n\n"
        f"💡 Пользователь получил уведомление.",
        reply_markup=get_back_to_main_menu().as_markup(),
        parse_mode="HTML"
    )
    
    audit_logger.info(f"ACTION:PROXY_ISSUED | ADMIN:{message.from_user.id} | USER:{target_user_id} | NAME:{proxy_name}")
    await state.clear()


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
