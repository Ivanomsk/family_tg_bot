from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
import os, re, logging
from datetime import datetime

from config import ADMIN_IDS, VPN_DIR, STATS_FILE, USER_PROXIES_FILE, BACKUP_DIR, PROXY_EXPIRY_DAYS, VPN_EXPIRY_DAYS
from utils.auto_delete import schedule_delete, delete_temp, delete_user, delete_proxy_card, delete_admin
from utils.expiry import check_all_vpn_expiry, check_all_proxy_expiry
from utils.audit import log_admin_action
from database.storage import load_json, save_json

router = Router()
logger = logging.getLogger(__name__)

del_file_cache = {}
del_pending = {}

def get_safe_dir(username):
    return os.path.join(VPN_DIR, re.sub(r'[^\w\-]', '_', username))

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только админ", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    log_admin_action(message.from_user.id, "VIEW_STATS", "Просмотр статистики")
    
    stats = load_json(STATS_FILE, {})
    if not stats:
        msg = await message.answer("📊 Статистики пока нет.", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    user_proxies = load_json(USER_PROXIES_FILE, {})
    text = "📊 <b>Статистика использования:</b>\n\n"
    sorted_users = sorted(stats.items(), key=lambda x: sum(x[1].get("actions", {}).values()), reverse=True)

    for uid, data in sorted_users:
        username = data.get("username") or "Unknown"
        name = data.get("name") or username
        total = sum(data.get("actions", {}).values())
        vpn = data.get("actions", {}).get("vpn", 0)
        uploaded = data.get("actions", {}).get("config_uploaded", 0)
        proxy_req = data.get("actions", {}).get("proxy_request", 0)
        proxy_count = len(user_proxies.get(uid, {}).get("proxies", []))
        
        text += f"👤 <b>{name}</b> (@{username})\n"
        text += f"   📱 Действий: {total} | 🔐 VPN: {vpn} | 📤 Конфигов: {uploaded}\n"
        text += f"   🛰 Запросов прокси: {proxy_req} | Активных прокси: {proxy_count}\n\n"

    msg = await message.answer(text, parse_mode="HTML")
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.message(Command("configs"))
async def cmd_configs(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только админ", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    
    text = "📂 <b>Структура конфигов:</b>\n\n"
    if not os.path.exists(VPN_DIR):
        msg = await message.answer("📁 Папка пуста.", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    del_file_cache.clear()
    found = False
    del_index = 0

    for user_folder in sorted(os.listdir(VPN_DIR)):
        user_path = os.path.join(VPN_DIR, user_folder)
        if os.path.isdir(user_path):
            files = [f for f in os.listdir(user_path) if f.endswith('.vpn')]
            if files:
                text += f"📁 <b>@{user_folder}</b> ({len(files)} файлов):\n"
                builder = InlineKeyboardBuilder()
                for f in sorted(files):
                    text += f"  ✅ {f}\n"
                    del_key = f"del_{del_index}"
                    del_file_cache[del_key] = (user_folder, f)
                    builder.button(text=f"🗑 {f.replace('.vpn', '')}", callback_data=del_key)
                    del_index += 1
                builder.button(text=f"🧹 Очистить всё @{user_folder}", callback_data=f"clear_{user_folder}")
                builder.adjust(1)
                text += "\n"
                msg = await message.answer(text, parse_mode="HTML", reply_markup=builder.as_markup())
                delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
                text = ""
                found = True

    if not found:
        msg = await message.answer("📂 <b>Файлов пока нет.</b>", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
    elif text:
        msg = await message.answer(text, parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.callback_query(F.data.startswith("del_"))
async def process_delete_confirm(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    await callback.answer()
    cache_key = callback.data
    file_info = del_file_cache.get(cache_key)
    if not file_info:
        msg = await callback.message.answer("❌ Файл не найден в кэше. Обнови список через /configs", parse_mode="HTML")
        delete_admin(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)
        return

    username, filename = file_info
    del_pending[f"delete_{callback.from_user.id}"] = {"username": username, "filename": filename, "cache_key": cache_key}

    msg = await callback.message.answer(f"⚠️ <b>Подтверждение удаления</b>\n\n👤 Пользователь: @{username}\n📁 Файл: {filename}\n\nНапиши <b>ДА</b> для удаления или /cancel для отмены", parse_mode="HTML")
    delete_admin(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)

@router.message(F.text.lower().in_({"да", "yes", "подтверждаю"}))
async def confirm_delete(message: types.Message):
    if message.from_user.id not in ADMIN_IDS: return
    key = f"delete_{message.from_user.id}"
    info = del_pending.get(key)
    if not info:
        msg = await message.answer("❌ Нет активного запроса на удаление.", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    
    username, filename, cache_key = info["username"], info["filename"], info["cache_key"]
    user_dir = get_safe_dir(username)
    file_path = os.path.join(user_dir, filename)

    if os.path.exists(file_path):
        os.remove(file_path)
        msg = await message.answer(f"✅ Файл <b>{filename}</b> удалён у @{username}", parse_mode="HTML")
        if not os.listdir(user_dir): os.rmdir(user_dir)
    else:
        msg = await message.answer(f"❌ Файл уже не существует.", parse_mode="HTML")
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

    if cache_key in del_file_cache: del del_file_cache[cache_key]
    if key in del_pending: del del_pending[key]

@router.message(Command("delconfig"))
async def cmd_delconfig(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только админ", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        msg = await message.answer("🗑 <b>Удаление конфига:</b>\n\nФормат: <code>/delconfig username filename.vpn</code>\n\nПример: <code>/delconfig Ivan_Mos iPhone_02.06.vpn</code>", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    username, filename = parts[1].lstrip('@'), parts[2]
    log_admin_action(message.from_user.id, "DELETE_CONFIG", f"User: @{username}, File: {filename}")

    user_dir = get_safe_dir(username)
    file_path = os.path.join(user_dir, filename)

    if not os.path.exists(file_path):
        msg = await message.answer(f"❌ Файл <b>{filename}</b> не найден у @{username}", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    os.remove(file_path)
    msg = await message.answer(f"✅ Файл <b>{filename}</b> удалён у @{username}", parse_mode="HTML")
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
    if not os.listdir(user_dir): os.rmdir(user_dir)

@router.message(Command("clearuser"))
async def cmd_clearuser(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только админ", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        msg = await message.answer("🗑 <b>Очистка всех конфигов:</b>\n\nФормат: <code>/clearuser username</code>", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    username = parts[1].lstrip('@')
    log_admin_action(message.from_user.id, "CLEAR_USER", f"User: @{username}")
    user_dir = get_safe_dir(username)

    files = [f for f in os.listdir(user_dir) if f.endswith('.vpn')]
    if not files:
        msg = await message.answer(f"❌ У @{username} нет конфигов.", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    for f in files: os.remove(os.path.join(user_dir, f))
    os.rmdir(user_dir)

    msg = await message.answer(f"✅ У @{username} удалено конфигов: <b>{len(files)}</b>", parse_mode="HTML")
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.callback_query(F.data.startswith("clear_"))
async def clear_user_configs(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    await callback.answer()
    username = callback.data.replace("clear_", "")
    user_dir = get_safe_dir(username)
    files = [f for f in os.listdir(user_dir) if f.endswith('.vpn')]
    if not files:
        msg = await callback.message.answer(f"❌ У @{username} нет конфигов.", parse_mode="HTML")
        delete_admin(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)
        return

    for f in files: os.remove(os.path.join(user_dir, f))
    os.rmdir(user_dir)

    msg = await callback.message.answer(f"✅ У @{username} удалено конфигов: <b>{len(files)}</b>", parse_mode="HTML")
    delete_admin(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)

@router.message(Command("clearproxy"))
async def cmd_clearproxy(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только админ", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        msg = await message.answer("🗑 <b>Удаление прокси пользователя:</b>\n\nФормат: <code>/clearproxy username</code> или <code>/clearproxy user_id</code>", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    target = parts[1].lstrip('@').lower()
    log_admin_action(message.from_user.id, "CLEAR_PROXY", f"Target: {target}")
    user_proxies = load_json(USER_PROXIES_FILE, {})
    user_id_to_delete = None

    if target.isdigit() and target in user_proxies:
        user_id_to_delete = target
    else:
        stats = load_json(STATS_FILE, {})
        for uid, data in stats.items():
            if (data.get("username") or "").lower() == target and uid in user_proxies:
                user_id_to_delete = uid
                break

    if user_id_to_delete and user_id_to_delete in user_proxies:
        del user_proxies[user_id_to_delete]
        save_json(USER_PROXIES_FILE, user_proxies)
        msg = await message.answer(f"✅ Все прокси удалены для пользователя ID {user_id_to_delete}", parse_mode="HTML")
    else:
        msg = await message.answer(f"❌ Прокси не найдены для @{target}", parse_mode="HTML")
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.message(Command("check_vpn_expiry"))
async def cmd_check_vpn_expiry(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только админ", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    log_admin_action(message.from_user.id, "CHECK_VPN_EXPIRY", "Проверка срока VPN")
    expired, expiring_soon = check_all_vpn_expiry()

    text = f"🔍 <b>Проверка VPN конфигов</b>\n⏰ Срок действия: <b>{VPN_EXPIRY_DAYS} дней</b>\n\n"
    if expired:
        text += f"❌ <b>ИСТЕКЛИ ({len(expired)}):</b>\n"
        for item in expired: text += f"  • @{item['username']} — <b>{item['filename']}</b> (просрочен на {item['days_expired']} дн.)\n"
        text += "\n"
    else: text += "✅ Истёкших VPN конфигов нет\n\n"

    if expiring_soon:
        text += f"⚠️ <b>ИСТЕКАЮТ СКОРО ({len(expiring_soon)}):</b>\n"
        for item in expiring_soon: text += f"  • @{item['username']} — <b>{item['filename']}</b> (осталось: <b>{item['days_left']} дн.</b>)\n"
    else: text += "✅ Скоро истекающих VPN конфигов нет\n"

    msg = await message.answer(text, parse_mode="HTML")
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.message(Command("check_proxy_expiry"))
async def cmd_check_proxy_expiry(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только админ", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return
    log_admin_action(message.from_user.id, "CHECK_PROXY_EXPIRY", "Проверка срока прокси")
    
    user_proxies = load_json(USER_PROXIES_FILE, {})
    now = datetime.now()
    expired_users, expiring_soon_users = [], []

    for user_id_str, data in user_proxies.items():
        if "proxies" not in data: continue
        for proxy in data["proxies"]:
            if "issued_at" not in proxy: continue
            try:
                issued_at = datetime.fromisoformat(proxy["issued_at"])
                days_left = PROXY_EXPIRY_DAYS - (now - issued_at).days
                try:
                    user = await message.bot.get_chat(int(user_id_str))
                    username = user.username or f"ID:{user_id_str}"
                except Exception: username = f"ID:{user_id_str}"

                if days_left < 0:
                    expired_users.append({"username": username, "proxy_name": proxy.get("name", "Без названия"), "days_expired": abs(days_left), "issued_at": issued_at.strftime("%d.%m.%Y")})
                elif days_left <= 7:
                    expiring_soon_users.append({"username": username, "proxy_name": proxy.get("name", "Без названия"), "days_left": days_left, "issued_at": issued_at.strftime("%d.%m.%Y")})
            except Exception as e: logger.error(f"Ошибка проверки прокси для {user_id_str}: {e}")

    text = f"🔍 <b>Проверка срока прокси</b>\n⏰ Срок действия: <b>{PROXY_EXPIRY_DAYS} дней</b>\n\n"
    if expired_users:
        text += f"❌ <b>ИСТЕКЛИ ({len(expired_users)}):</b>\n"
        for u in expired_users: text += f"  • @{u['username']} — <b>{u['proxy_name']}</b> (выдан: {u['issued_at']}, просрочен на {u['days_expired']} дн.)\n"
        text += "\n"
    else: text += "✅ Истёкших прокси нет\n\n"

    if expiring_soon_users:
        text += f"⚠️ <b>ИСТЕКАЮТ СКОРО ({len(expiring_soon_users)}):</b>\n"
        for u in expiring_soon_users: text += f"  • @{u['username']} — <b>{u['proxy_name']}</b> (осталось: <b>{u['days_left']} дн.</b>)\n"
    else: text += "✅ Скоро истекающих прокси нет\n"

    msg = await message.answer(text, parse_mode="HTML")
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    is_admin = message.from_user.id in ADMIN_IDS
    if is_admin:
        text = ("📚 <b>ПОЛНЫЙ СПРАВОЧНИК</b>\n\n📱 <b>ПОЛЬЗОВАТЕЛЬСКИЕ:</b>\n🔐 <b>/vpn</b> — VPN конфиги\n🛰 <b>/request_proxy</b> — запрос прокси\n👁 <b>/my_proxy</b> — мои прокси\nℹ️ <b>/help</b> — справка\n\n━━━━━━━━━━━━━━━━━━━━\n\n👨‍💼 <b>АДМИНИСТРАТИВНЫЕ:</b>\n📊 <b>/stats</b> — статистика\n📂 <b>/configs</b> — управление конфигами\n🗑 <b>/delconfig user файл</b>\n🗑 <b>/clearuser user</b>\n🗑 <b>/clearproxy user</b>\n📦 <b>/backup</b>\n🔍 <b>/check_proxy_expiry</b>\n🔍 <b>/check_vpn_expiry</b>\n🧹 <b>/cleanup_backups</b>\n📋 <b>/list_backups</b>")
    else:
        text = ("📚 <b>СПРАВОЧНИК</b>\n\n🔐 <b>/vpn</b> — VPN конфиги\n🛰 <b>/request_proxy</b> — запрос прокси\n👁 <b>/my_proxy</b> — мои прокси\nℹ️ <b>/help</b> — справка")

    msg = await message.answer(text, parse_mode="HTML")
    if is_admin:
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
    else:
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

# ============================================================================
# ПУБЛИКАЦИЯ ОБНОВЛЕНИЙ AMNEZIA
# ============================================================================

@router.message(Command("news_amnezia"), F.from_user.id.in_(ADMIN_IDS))
async def cmd_news_amnezia(message: types.Message):
    """Публикация универсального шаблона Amnezia"""
    from web.amnezia_config import UNIVERSAL_TEMPLATE, AMNEZIA_LINKS, VERSION_CONFLICT_WARNING
    from keyboards.inline import get_news_confirm_keyboard
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    links_text = UNIVERSAL_TEMPLATE["links_section"].format(**AMNEZIA_LINKS)
    text = (
        f"{UNIVERSAL_TEMPLATE['title']}\n\n"
        f"{UNIVERSAL_TEMPLATE['body']}\n\n"
        f"{links_text}\n\n"
        f"{VERSION_CONFLICT_WARNING}"
    )
    
    keyboard = InlineKeyboardBuilder()
    for row in UNIVERSAL_TEMPLATE["buttons"]:
        for btn in row:
            keyboard.button(text=btn["text"], url=AMNEZIA_LINKS[btn["url"]])
        keyboard.adjust(len(row))
    
    await message.answer(
        text,
        reply_markup=keyboard.as_markup(),
        parse_mode="HTML",
        disable_web_page_preview=False
    )
    
    confirm_kb = get_news_confirm_keyboard()
    msg = await message.answer(
        "📢 Опубликовать это сообщение в общий чат?",
        reply_markup=confirm_kb
    )
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)


@router.callback_query(F.data == "news_confirm_publish")
async def process_news_confirm(callback: types.CallbackQuery):
    """Подтверждение публикации новости Amnezia"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(" Доступ запрещён", show_alert=True)
        return
    
    from web.amnezia_config import UNIVERSAL_TEMPLATE, AMNEZIA_LINKS, VERSION_CONFLICT_WARNING
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    links_text = UNIVERSAL_TEMPLATE["links_section"].format(**AMNEZIA_LINKS)
    text = (
        f"{UNIVERSAL_TEMPLATE['title']}\n\n"
        f"{UNIVERSAL_TEMPLATE['body']}\n\n"
        f"{links_text}\n\n"
        f"{VERSION_CONFLICT_WARNING}"
    )
    
    keyboard = InlineKeyboardBuilder()
    for row in UNIVERSAL_TEMPLATE["buttons"]:
        for btn in row:
            keyboard.button(text=btn["text"], url=AMNEZIA_LINKS[btn["url"]])
        keyboard.adjust(len(row))
    
    try:
        await callback.bot.send_message(
            chat_id=ALLOWED_CHAT_ID,
            text=text,
            reply_markup=keyboard.as_markup(),
            parse_mode="HTML",
            disable_web_page_preview=False
        )
        await callback.message.delete()
        msg = await callback.message.answer("✅ Новость опубликована!")
        delete_admin(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)
        log_admin_action(callback.from_user.id, "NEWS_AMNEZIA_PUBLISH", "Публикация обновления Amnezia")
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data == "news_cancel")
async def process_news_cancel(callback: types.CallbackQuery):
    """Отмена публикации новости"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer(" Доступ запрещён", show_alert=True)
        return
    
    await callback.message.delete()
    msg = await callback.message.answer("❌ Публикация отменена")
    delete_admin(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)

# ============================================================================
# КНОПКА AMNEZIA В МЕНЮ
# ============================================================================

@router.callback_query(F.data == "menu_amnezia_update")
async def process_amnezia_update(callback: types.CallbackQuery):
    """Обработка кнопки Amnezia VPN из меню"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return
    
    await callback.answer()
    
    # Вызываем функцию публикации Amnezia
    from web.amnezia_config import UNIVERSAL_TEMPLATE, AMNEZIA_LINKS, VERSION_CONFLICT_WARNING
    from keyboards.inline import get_news_confirm_keyboard
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from config import ALLOWED_CHAT_ID
    
    links_text = UNIVERSAL_TEMPLATE["links_section"].format(**AMNEZIA_LINKS)
    text = (
        f"{UNIVERSAL_TEMPLATE['title']}\n\n"
        f"{UNIVERSAL_TEMPLATE['body']}\n\n"
        f"{links_text}\n\n"
        f"{VERSION_CONFLICT_WARNING}"
    )
    
    keyboard = InlineKeyboardBuilder()
    for row in UNIVERSAL_TEMPLATE["buttons"]:
        for btn in row:
            keyboard.button(text=btn["text"], url=AMNEZIA_LINKS[btn["url"]])
        keyboard.adjust(len(row))
    
    await callback.message.answer(
        text,
        reply_markup=keyboard.as_markup(),
        parse_mode="HTML",
        disable_web_page_preview=False
    )
    
    confirm_kb = get_news_confirm_keyboard()
    msg = await callback.message.answer(
        "📢 Опубликовать это сообщение в общий чат?",
        reply_markup=confirm_kb
    )
    delete_admin(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)