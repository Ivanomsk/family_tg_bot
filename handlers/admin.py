from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS, VPN_DIR, BACKUP_DIR
from utils.auto_delete import delete_admin, delete_temp
from utils.logger import standard_logger, audit_logger
from database.storage import load_json, save_json
from utils.vpn_manager import load_vpn_db, save_vpn_db, revoke_vpn_config
from handlers.start import get_user_dir, get_user_configs
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


@router.callback_query(F.data == "menu_stats")
async def menu_stats(callback: types.CallbackQuery):
    """Статистика"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    # Импортируем и вызываем статистику из handlers/start.py
    from handlers.start import admin_stats
    await admin_stats(callback)


@router.callback_query(F.data == "admin_check_expiry")
async def admin_check_expiry(callback: types.CallbackQuery):
    """Проверка сроков"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    from handlers.start import admin_check_expiry
    await admin_check_expiry(callback)


@router.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    """Управление пользователями"""
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


@router.callback_query(F.data == "menu_backup")
async def menu_backup(callback: types.CallbackQuery):
    """Меню бэкапов"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    text = (
        "📦 <b>УПРАВЛЕНИЕ БЭКАПАМИ</b>\n\n"
        "💡 <b>Используйте команды:</b>\n\n"
        "<code>/backup</code> — создать резервную копию\n"
        "<code>/list_backups</code> — показать все бэкапы\n"
        "<code>/cleanup_backups N</code> — оставить N последних бэкапов\n\n"
        "📝 <b>Примеры:</b>\n"
        "<code>/backup</code>\n"
        "<code>/list_backups</code>\n"
        "<code>/cleanup_backups 5</code>\n\n"
        "🤖 <b>Автобэкап:</b>\n"
        "• Каждый день в 03:00\n"
        "• Хранится 7 последних\n"
        "• Уведомление приходит в ЛС"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_admin_main").as_markup()
    )


@router.callback_query(F.data == "news_start")
async def news_start(callback: types.CallbackQuery):
    """Публикация новости"""
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
    """Обычная новость"""
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
    """Анонс обновления Amnezia VPN"""
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
    """Опубликовать анонс обновления в чат"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    from config import ALLOWED_CHAT_ID
    
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


@router.callback_query(F.data == "admin_vpn_list")
async def admin_vpn_list(callback: types.CallbackQuery):
    """Список VPN пользователей"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    vpn_users = load_vpn_db()
    if not vpn_users:
        await callback.message.edit_text(
            "📭 Нет активных VPN конфигов.",
            reply_markup=get_back_keyboard("admin_users").as_markup(),
            parse_mode="HTML"
        )
        return
    
    users = {}
    for public_key, data in vpn_users.items():
        username = data.get('username', 'unknown')
        user_id_data = data.get('user_id')
        active = data.get('active', True)
        permanent = data.get('permanent', False)
        expires_at = data.get('expires_at', 'не указана')
        
        if expires_at != 'не указана':
            try:
                dt = datetime.fromisoformat(expires_at)
                expires_display = dt.strftime('%d.%m.%Y %H:%M')
            except:
                expires_display = expires_at
        else:
            expires_display = 'не указана'
        
        if username not in users:
            users[username] = {
                'user_id': user_id_data,
                'configs': [],
                'total': 0
            }
        users[username]['configs'].append({
            'active': active,
            'permanent': permanent,
            'expires_at': expires_display
        })
        users[username]['total'] += 1
    
    text = "📋 <b>СПИСОК VPN ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
    
    for username, data in sorted(users.items()):
        user_id_data = data['user_id']
        username_display = f"@{username}" if username != 'unknown' else f"ID:{user_id_data}"
        text += f"👤 {username_display} (ID: {user_id_data})\n"
        text += f"   📁 Конфигов: {data['total']}\n"
        for conf in data['configs']:
            if conf['permanent']:
                status = "♾️ Бессрочный"
            elif conf['active']:
                status = "✅ Активен"
            else:
                status = "❌ Неактивен"
            text += f"      {status} | истекает: {conf['expires_at']}\n"
        text += "\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_users").as_markup()
    )


@router.callback_query(F.data == "admin_vpn_revoke")
async def admin_vpn_revoke_menu(callback: types.CallbackQuery):
    """Меню отзыва VPN"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    text = (
        "🗑️ <b>ОТОЗВАТЬ VPN</b>\n\n"
        "Используйте команду:\n"
        "<code>/revoke username</code> — отозвать ВСЕ конфиги пользователя\n"
        "<code>/revoke username public_key</code> — отозвать конкретный\n\n"
        "📝 <b>Примеры:</b>\n"
        "<code>/revoke Ivan_Mos</code>\n"
        "<code>/revoke Ivan_Mos pXsM/uIIRo0xv0AMTnVF</code>\n\n"
        "💡 <i>Конфиг будет удалён с сервера и помечен как неактивный</i>"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_users").as_markup()
    )


@router.callback_query(F.data == "admin_proxy_list")
async def admin_proxy_list(callback: types.CallbackQuery):
    """Список прокси"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    user_proxies = load_json("bot_data/user_proxies.json", {})
    if not user_proxies:
        await callback.message.edit_text(
            "📭 Нет пользователей с прокси.",
            reply_markup=get_back_keyboard("admin_users").as_markup(),
            parse_mode="HTML"
        )
        return
    
    stats = load_json("bot_data/stats.json", {})
    
    text = "🛰 <b>Список прокси пользователей</b>\n\n"
    
    for user_id_str, data in user_proxies.items():
        user_id = int(user_id_str)
        proxies = data.get("proxies", [])
        
        if proxies:
            username = stats.get(user_id_str, {}).get('username')
            if username:
                display_name = f"@{username} (ID: {user_id_str})"
            else:
                display_name = f"ID: {user_id_str}"
            
            text += f"👤 {display_name} ({len(proxies)}):\n"
            for p in proxies:
                is_permanent = p.get('permanent', False)
                status = "♾️" if is_permanent else "📅"
                text += f"  {status} {p.get('name')} | {p.get('server')}:{p.get('port')}\n"
            text += "\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_users").as_markup()
    )


@router.callback_query(F.data == "admin_permanent_menu")
async def admin_permanent_menu(callback: types.CallbackQuery):
    """Бессрочный VPN"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    vpn_users = load_vpn_db()
    if not vpn_users:
        await callback.message.edit_text(
            "📭 Нет пользователей с конфигами.",
            reply_markup=get_back_keyboard("menu_admin_main").as_markup(),
            parse_mode="HTML"
        )
        return
    
    users = {}
    for ch, cd in vpn_users.items():
        username = cd.get('username', 'unknown')
        if username not in users:
            users[username] = []
        users[username].append({
            'hash': ch,
            'permanent': cd.get('permanent', False),
            'active': cd.get('active', True)
        })
    
    text = (
        "♾️ <b>Управление бессрочным статусом VPN</b>\n\n"
        "💡 <b>Используйте команду:</b>\n"
        "<code>/permanent username filename on/off</code>\n\n"
        "📝 <b>Примеры:</b>\n"
        "<code>/permanent Ivan_Mos Для_пк_Исиль.vpn on</code>\n"
        "<code>/permanent Ivan_Mos Для_пк_Исиль.vpn off</code>\n\n"
        "📋 <b>Список пользователей:</b>\n"
    )
    
    for username, configs in users.items():
        active_count = sum(1 for c in configs if c['active'])
        username_display = f"@{username}" if username else "unknown"
        text += f"\n👤 {username_display} ({active_count} конфигов)"
        for c in configs:
            status = "♾️" if c['permanent'] else "📅"
            active = "✅" if c['active'] else "❌"
            text += f"\n  {status} {active} {c['hash'][:20]}..."
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_admin_main").as_markup()
    )


@router.callback_query(F.data == "admin_permanent_proxy_menu")
async def admin_permanent_proxy_menu(callback: types.CallbackQuery):
    """Бессрочный прокси"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    user_proxies = load_json("bot_data/user_proxies.json", {})
    if not user_proxies:
        await callback.message.edit_text(
            "📭 Нет пользователей с прокси.",
            reply_markup=get_back_keyboard("menu_admin_main").as_markup(),
            parse_mode="HTML"
        )
        return
    
    stats = load_json("bot_data/stats.json", {})
    
    text = (
        "♾️ <b>Управление бессрочным статусом прокси</b>\n\n"
        "💡 <b>Используйте команду:</b>\n"
        "<code>/permanent_proxy user_id имя_прокси on/off</code>\n\n"
        "📝 <b>Примеры:</b>\n"
        "<code>/permanent_proxy 764438696 Основной on</code>\n"
        "<code>/permanent_proxy 764438696 Основной off</code>\n\n"
        "📋 <b>Список пользователей с прокси:</b>\n"
    )
    
    from utils.expiry import is_proxy_expired
    
    for user_id_str, data in user_proxies.items():
        user_id = int(user_id_str)
        proxies = data.get("proxies", [])
        active_proxies = [p for p in proxies if not is_proxy_expired(user_id, p.get('name'))]
        
        if active_proxies:
            username = stats.get(user_id_str, {}).get('username')
            if username:
                display_name = f"@{username} (ID: {user_id_str})"
            else:
                display_name = f"ID: {user_id_str}"
            
            text += f"\n👤 {display_name} ({len(active_proxies)} прокси)"
            for p in active_proxies:
                status = "♾️" if p.get('permanent', False) else "📅"
                text += f"\n  {status} {p.get('name')}"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_admin_main").as_markup()
    )


# ==========================================
# АДМИН-ПАНЕЛЬ - КОМАНДЫ
# ==========================================

@router.message(Command("configs"))
async def cmd_configs(message: types.Message):
    if not await admin_private_only(message):
        return
    
    if not os.path.exists(VPN_DIR):
        await message.answer("📭 Папка с конфигами пуста.")
        return
    
    users_dirs = [d for d in os.listdir(VPN_DIR) if os.path.isdir(os.path.join(VPN_DIR, d))]
    
    if not users_dirs:
        await message.answer("📭 Нет пользователей с конфигами.")
        return
    
    text = "📂 <b>СПИСОК ВСЕХ КОНФИГОВ</b>\n\n"
    
    for user_dir in sorted(users_dirs):
        user_path = os.path.join(VPN_DIR, user_dir)
        configs = [f for f in os.listdir(user_path) if f.endswith('.vpn')]
        if configs:
            text += f"👤 @{user_dir} ({len(configs)}):\n"
            for conf in configs:
                text += f"  • {conf}\n"
            text += "\n"
    
    await message.answer(text, parse_mode="HTML")


@router.message(Command("delconfig"))
async def cmd_delconfig(message: types.Message):
    if not await admin_private_only(message):
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Используйте: <code>/delconfig username имя_файла.vpn</code>\n"
            "Пример: <code>/delconfig Ivan_Mos Для_пк_Исиль.vpn</code>",
            parse_mode="HTML"
        )
        return
    
    username = parts[1]
    filename = parts[2]
    
    user_dir = os.path.join(VPN_DIR, username)
    file_path = os.path.join(user_dir, filename)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        await message.answer(f"✅ Конфиг <b>{filename}</b> удалён.", parse_mode="HTML")
        audit_logger.info(f"ACTION:DELETE_CONFIG | ADMIN:{message.from_user.id} | USER:{username} | FILE:{filename}")
    else:
        await message.answer(f"❌ Файл <b>{filename}</b> не найден.", parse_mode="HTML")


@router.message(Command("clearuser"))
async def cmd_clearuser(message: types.Message):
    if not await admin_private_only(message):
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Используйте: <code>/clearuser username</code>\n"
            "Пример: <code>/clearuser Ivan_Mos</code>",
            parse_mode="HTML"
        )
        return
    
    username = parts[1]
    user_dir = os.path.join(VPN_DIR, username)
    
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)
        await message.answer(f"✅ Все конфиги пользователя <b>{username}</b> удалены.", parse_mode="HTML")
        audit_logger.info(f"ACTION:CLEAR_USER | ADMIN:{message.from_user.id} | USER:{username}")
    else:
        await message.answer(f"❌ Пользователь <b>{username}</b> не найден.", parse_mode="HTML")


@router.message(Command("clearproxy"))
async def cmd_clearproxy(message: types.Message):
    if not await admin_private_only(message):
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Используйте: <code>/clearproxy username</code>\n"
            "Пример: <code>/clearproxy Ivan_Mos</code>",
            parse_mode="HTML"
        )
        return
    
    username = parts[1]
    user_proxies = load_json("bot_data/user_proxies.json", {})
    
    found = False
    for uid, data in list(user_proxies.items()):
        if data.get("username") == username or data.get("name") == username:
            del user_proxies[uid]
            found = True
    
    if found:
        save_json("bot_data/user_proxies.json", user_proxies)
        await message.answer(f"✅ Прокси пользователя <b>{username}</b> удалены.", parse_mode="HTML")
        audit_logger.info(f"ACTION:CLEAR_PROXY | ADMIN:{message.from_user.id} | USER:{username}")
    else:
        await message.answer(f"❌ Пользователь <b>{username}</b> не найден.", parse_mode="HTML")


@router.message(Command("permanent"))
async def cmd_permanent(message: types.Message):
    if not await admin_private_only(message):
        return
    
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Используйте:\n"
            "<code>/permanent username filename on</code> — сделать бессрочным\n"
            "<code>/permanent username filename off</code> — убрать бессрочный\n\n"
            "📝 <b>Примеры:</b>\n"
            "<code>/permanent Ivan_Mos Для_пк_Исиль.vpn on</code>\n"
            "<code>/permanent Ivan_Mos Для_пк_Исиль.vpn off</code>",
            parse_mode="HTML"
        )
        return
    
    username = parts[1]
    filename = parts[2]
    action = parts[3].lower()
    
    if action not in ["on", "off"]:
        await message.answer("❌ Действие должно быть <code>on</code> или <code>off</code>", parse_mode="HTML")
        return
    
    vpn_users = load_vpn_db()
    found = False
    
    for ch, cd in vpn_users.items():
        if cd.get('username') == username and cd.get('active', True):
            user_dir = get_user_dir(username)
            if os.path.exists(os.path.join(user_dir, filename)):
                found = True
                if action == "on":
                    cd['permanent'] = True
                    status_text = f"♾️ Бессрочный (конфиг: {filename})"
                else:
                    cd.pop('permanent', None)
                    if 'expires_at' not in cd or cd.get('expires_at') == "бессрочно":
                        new_expires = datetime.now() + timedelta(days=30)
                        cd['expires_at'] = new_expires.isoformat()
                    status_text = f"🔄 Обычный (30 дней) (конфиг: {filename})"
                
                vpn_users[ch] = cd
                save_vpn_db(vpn_users)
                
                await message.answer(
                    f"✅ <b>Статус обновлён!</b>\n\n"
                    f"👤 Пользователь: @{username}\n"
                    f"📁 Конфиг: {filename}\n"
                    f"📊 Новый статус: {status_text}",
                    parse_mode="HTML"
                )
                audit_logger.info(f"ACTION:PERMANENT | ADMIN:{message.from_user.id} | USER:{username} | FILE:{filename} | {action}")
                return
    
    if not found:
        await message.answer(
            f"❌ Конфиг <b>{filename}</b> для пользователя @{username} не найден.\n\n"
            f"Проверьте имя файла (с расширением .vpn).",
            parse_mode="HTML"
        )


@router.message(Command("permanent_proxy"))
async def cmd_permanent_proxy(message: types.Message):
    if not await admin_private_only(message):
        return
    
    parts = message.text.split(maxsplit=3)
    if len(parts) < 4:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Используйте:\n"
            "<code>/permanent_proxy user_id proxy_name on</code> — бессрочный\n"
            "<code>/permanent_proxy user_id proxy_name off</code> — убрать бессрочный\n\n"
            "📝 <b>Примеры:</b>\n"
            "<code>/permanent_proxy 764438696 Основной on</code>\n"
            "<code>/permanent_proxy 764438696 Основной off</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        target_user_id = int(parts[1])
    except ValueError:
        await message.answer("❌ ID пользователя должен быть числом.")
        return
    
    proxy_name = parts[2]
    action = parts[3].lower()
    
    if action not in ["on", "off"]:
        await message.answer("❌ Действие должно быть <code>on</code> или <code>off</code>", parse_mode="HTML")
        return
    
    user_proxies = load_json("bot_data/user_proxies.json", {})
    user_id_str = str(target_user_id)
    
    if user_id_str not in user_proxies:
        await message.answer(f"❌ Пользователь ID {target_user_id} не найден.")
        return
    
    proxies = user_proxies[user_id_str].get("proxies", [])
    found = False
    
    for proxy in proxies:
        if proxy.get('name') == proxy_name:
            found = True
            if action == "on":
                proxy['permanent'] = True
                status_text = f"♾️ Бессрочный (прокси: {proxy_name})"
            else:
                proxy.pop('permanent', None)
                if 'issued_at' not in proxy:
                    proxy['issued_at'] = datetime.now().isoformat()
                status_text = f"🔄 Обычный (30 дней) (прокси: {proxy_name})"
            
            user_proxies[user_id_str]["proxies"] = proxies
            save_json("bot_data/user_proxies.json", user_proxies)
            
            await message.answer(
                f"✅ <b>Статус обновлён!</b>\n\n"
                f"👤 Пользователь ID: {target_user_id}\n"
                f"📁 Прокси: {proxy_name}\n"
                f"📊 Новый статус: {status_text}",
                parse_mode="HTML"
            )
            audit_logger.info(f"ACTION:PERMANENT_PROXY | ADMIN:{message.from_user.id} | USER:{target_user_id} | PROXY:{proxy_name} | {action}")
            return
    
    if not found:
        await message.answer(
            f"❌ Прокси <b>{proxy_name}</b> у пользователя ID {target_user_id} не найден.",
            parse_mode="HTML"
        )


@router.message(Command("revoke"))
async def cmd_revoke(message: types.Message):
    if not await admin_private_only(message):
        return
    
    parts = message.text.split(maxsplit=2)
    if len(parts) < 2:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Используйте:\n"
            "<code>/revoke username</code> — отозвать ВСЕ конфиги\n"
            "<code>/revoke username public_key</code> — отозвать конкретный\n\n"
            "📝 <b>Примеры:</b>\n"
            "<code>/revoke Ivan_Mos</code>\n"
            "<code>/revoke Ivan_Mos pXsM/uIIRo0xv0AMTnVF</code>",
            parse_mode="HTML"
        )
        return
    
    username = parts[1]
    key_part = parts[2] if len(parts) > 2 else None
    
    vpn_users = load_vpn_db()
    found = False
    revoked_count = 0
    
    for public_key, data in list(vpn_users.items()):
        if data.get('username') != username:
            continue
        if not data.get('active', True):
            continue
        
        if key_part:
            if not public_key.startswith(key_part):
                continue
        
        result = revoke_vpn_config(public_key)
        if result.get('success'):
            revoked_count += 1
            found = True
            audit_logger.info(f"ACTION:REVOKE_VPN | ADMIN:{message.from_user.id} | USER:{username} | KEY:{public_key[:20]}...")
    
    if found:
        await message.answer(
            f"✅ <b>VPN конфиги отозваны!</b>\n\n"
            f"👤 Пользователь: @{username}\n"
            f"🗑️ Отозвано конфигов: {revoked_count}\n\n"
            f"💡 Пользователь больше не сможет использовать эти конфиги.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"❌ Пользователь @{username} не найден или не имеет активных конфигов.",
            parse_mode="HTML"
        )


@router.message(Command("userinfo"))
async def cmd_userinfo(message: types.Message):
    if not await admin_private_only(message):
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Используйте: <code>/userinfo @username</code>\n"
            "Пример: <code>/userinfo @Ivan_Mos</code>",
            parse_mode="HTML"
        )
        return
    
    username = parts[1].lstrip('@')
    
    vpn_users = load_vpn_db()
    stats = load_json("bot_data/stats.json", {})
    user_proxies = load_json("bot_data/user_proxies.json", {})
    
    user_configs = []
    user_id = None
    for key, data in vpn_users.items():
        if data.get('username') == username:
            user_id = data.get('user_id')
            user_configs.append({
                'key': key[:20] + '...',
                'active': data.get('active', True),
                'permanent': data.get('permanent', False),
                'expires_at': data.get('expires_at', 'не указана'),
                'ip': data.get('ip', '')
            })
    
    user_stats = None
    for uid, data in stats.items():
        if data.get('username') == username:
            user_stats = data
            if not user_id:
                user_id = int(uid)
            break
    
    user_proxies_list = []
    if user_id:
        proxies = user_proxies.get(str(user_id), {}).get("proxies", [])
        user_proxies_list = proxies
    
    text = f"👤 <b>ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ</b>\n\n"
    text += f"📌 <b>Username:</b> @{username}\n"
    if user_id:
        text += f"📌 <b>ID:</b> {user_id}\n"
    
    text += f"\n🔐 <b>VPN конфиги ({len(user_configs)}):</b>\n"
    if user_configs:
        for conf in user_configs:
            status = "♾️" if conf['permanent'] else "✅" if conf['active'] else "❌"
            text += f"   {status} {conf['key']}"
            if conf['expires_at'] != 'не указана':
                try:
                    dt = datetime.fromisoformat(conf['expires_at'])
                    text += f" | истекает: {dt.strftime('%d.%m.%Y %H:%M')}"
                except:
                    text += f" | истекает: {conf['expires_at']}"
            text += "\n"
    else:
        text += "   ❌ Нет активных конфигов\n"
    
    text += f"\n🛰 <b>Прокси ({len(user_proxies_list)}):</b>\n"
    if user_proxies_list:
        for proxy in user_proxies_list:
            status = "♾️" if proxy.get('permanent') else "📅"
            text += f"   {status} {proxy.get('name')} | {proxy.get('server')}:{proxy.get('port')}\n"
    else:
        text += "   ❌ Нет прокси\n"
    
    if user_stats:
        actions = user_stats.get('actions', {})
        total = sum(actions.values())
        text += f"\n📊 <b>Активность в боте:</b>\n"
        text += f"   📌 Всего действий: {total}\n"
        for action, count in actions.items():
            text += f"      • {action}: {count}\n"
    
    text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
    text += f"💡 <b>Команды для управления:</b>\n"
    text += f"<code>/revoke @{username}</code> — отозвать конфиги\n"
    text += f"<code>/deluser @{username}</code> — удалить полностью\n"
    text += f"<code>/clearuser {username}</code> — удалить файлы"
    
    await message.answer(text, parse_mode="HTML")


@router.message(Command("deluser"))
async def cmd_deluser(message: types.Message):
    if not await admin_private_only(message):
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Используйте: <code>/deluser @username</code>\n"
            "Пример: <code>/deluser @Ivan_Mos</code>\n\n"
            "⚠️ <b>Внимание!</b> Это удалит ВСЕ данные пользователя.",
            parse_mode="HTML"
        )
        return
    
    username = parts[1].lstrip('@')
    
    await message.answer(
        f"⚠️ <b>Вы уверены, что хотите удалить пользователя @{username}?</b>\n\n"
        f"Будут удалены:\n"
        f"• Все VPN конфиги\n"
        f"• Все прокси\n"
        f"• Вся статистика\n"
        f"• Все файлы\n\n"
        f"Для подтверждения отправьте:\n"
        f"<code>/deluser_confirm @{username}</code>",
        parse_mode="HTML"
    )


@router.message(Command("deluser_confirm"))
async def cmd_deluser_confirm(message: types.Message):
    if not await admin_private_only(message):
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("❌ Укажите username: <code>/deluser_confirm @username</code>", parse_mode="HTML")
        return
    
    username = parts[1].lstrip('@')
    
    vpn_users = load_vpn_db()
    revoked = 0
    for key, data in list(vpn_users.items()):
        if data.get('username') == username and data.get('active', True):
            result = revoke_vpn_config(key)
            if result.get('success'):
                revoked += 1
    
    to_delete = []
    for key, data in list(vpn_users.items()):
        if data.get('username') == username:
            to_delete.append(key)
    for key in to_delete:
        del vpn_users[key]
    save_vpn_db(vpn_users)
    
    user_dir = os.path.join(VPN_DIR, username)
    if os.path.exists(user_dir):
        shutil.rmtree(user_dir)
    
    stats = load_json("bot_data/stats.json", {})
    stats_to_delete = []
    for uid, data in list(stats.items()):
        if data.get('username') == username:
            stats_to_delete.append(uid)
    for uid in stats_to_delete:
        del stats[uid]
    save_json("bot_data/stats.json", stats)
    
    user_proxies = load_json("bot_data/user_proxies.json", {})
    proxies_to_delete = []
    for uid, data in list(user_proxies.items()):
        if data.get('username') == username:
            proxies_to_delete.append(uid)
    for uid in proxies_to_delete:
        del user_proxies[uid]
    save_json("bot_data/user_proxies.json", user_proxies)
    
    await message.answer(
        f"✅ <b>Пользователь @{username} полностью удалён!</b>\n\n"
        f"🗑️ Отозвано конфигов: {revoked}\n"
        f"🗑️ Удалено записей из БД: {len(to_delete)}\n"
        f"🗑️ Удалена папка: {user_dir}\n\n"
        f"💡 Пользователь может зарегистрироваться заново.",
        parse_mode="HTML"
    )
    
    audit_logger.info(f"ACTION:DELUSER | ADMIN:{message.from_user.id} | USER:{username}")


# ==========================================
# БЭКАПЫ
# ==========================================

@router.message(Command("backup"))
async def cmd_backup(message: types.Message):
    if not await admin_private_only(message):
        return
    
    await message.answer("⏳ Создаю бэкап...")
    
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_{timestamp}.tar.gz"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        
        with tarfile.open(backup_path, "w:gz") as tar:
            data_dirs = ['bot_data']
            for dir_name in data_dirs:
                dir_path = os.path.join('/opt/durdom-bot', dir_name)
                if os.path.exists(dir_path):
                    tar.add(dir_path, arcname=dir_name)
        
        size = os.path.getsize(backup_path)
        size_str = f"{size/1024:.2f} KB" if size < 1024*1024 else f"{size/1024/1024:.2f} MB"
        
        await message.answer(
            f"✅ <b>Бэкап создан!</b>\n\n"
            f"📁 Имя: {backup_name}\n"
            f"📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            f"📦 Размер: {size_str}\n"
            f"📂 Путь: {backup_path}",
            parse_mode="HTML"
        )
        
        audit_logger.info(f"ACTION:BACKUP_CREATE | ADMIN:{message.from_user.id} | FILE:{backup_name}")
        
    except Exception as e:
        await message.answer(f"❌ Ошибка создания бэкапа: {e}")
        logger.error(f"Ошибка создания бэкапа: {e}")


@router.message(Command("list_backups"))
async def cmd_list_backups(message: types.Message):
    if not await admin_private_only(message):
        return
    
    if not os.path.exists(BACKUP_DIR):
        await message.answer("📭 Папка с бэкапами пуста.")
        return
    
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith('.tar.gz'):
            file_path = os.path.join(BACKUP_DIR, f)
            mtime = os.path.getmtime(file_path)
            size = os.path.getsize(file_path)
            backups.append({
                'name': f,
                'date': datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M:%S'),
                'size': f"{size/1024:.2f} KB" if size < 1024*1024 else f"{size/1024/1024:.2f} MB"
            })
    
    if not backups:
        await message.answer("📭 Нет бэкапов.")
        return
    
    backups.sort(key=lambda x: x['date'], reverse=True)
    
    text = "📋 <b>СПИСОК БЭКАПОВ</b>\n\n"
    for b in backups[:10]:
        text += f"📁 {b['name']}\n"
        text += f"   📅 {b['date']} | 📦 {b['size']}\n\n"
    
    if len(backups) > 10:
        text += f"💡 ... и ещё {len(backups) - 10} бэкапов\n\n"
    
    text += "💡 <b>Команда для очистки:</b>\n"
    text += "<code>/cleanup_backups 5</code> — оставить 5 последних"
    
    await message.answer(text, parse_mode="HTML")


@router.message(Command("cleanup_backups"))
async def cmd_cleanup_backups(message: types.Message):
    if not await admin_private_only(message):
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ <b>Неверный формат</b>\n\n"
            "Используйте: <code>/cleanup_backups N</code>\n"
            "Пример: <code>/cleanup_backups 5</code> — оставить 5 последних",
            parse_mode="HTML"
        )
        return
    
    try:
        keep_count = int(parts[1])
    except ValueError:
        await message.answer("❌ N должно быть числом.")
        return
    
    if not os.path.exists(BACKUP_DIR):
        await message.answer("📭 Папка с бэкапами пуста.")
        return
    
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith('.tar.gz'):
            file_path = os.path.join(BACKUP_DIR, f)
            mtime = os.path.getmtime(file_path)
            backups.append({'name': f, 'path': file_path, 'mtime': mtime})
    
    if not backups:
        await message.answer("📭 Нет бэкапов.")
        return
    
    backups.sort(key=lambda x: x['mtime'], reverse=True)
    
    deleted = 0
    for b in backups[keep_count:]:
        os.remove(b['path'])
        deleted += 1
    
    await message.answer(
        f"✅ <b>Очистка завершена!</b>\n\n"
        f"🗑️ Удалено старых бэкапов: {deleted}\n"
        f"📁 Оставлено последних: {keep_count}",
        parse_mode="HTML"
    )
    
    audit_logger.info(f"ACTION:CLEANUP_BACKUPS | ADMIN:{message.from_user.id} | KEPT:{keep_count} | DELETED:{deleted}")
