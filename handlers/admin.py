from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS, VPN_DIR, BACKUP_DIR
from utils.auto_delete import delete_admin, delete_temp
from utils.logger import standard_logger, audit_logger
from database.storage import load_json, save_json
from utils.vpn_manager import load_vpn_db, save_vpn_db
from handlers.start import get_user_dir, get_user_configs
from keyboards.inline import get_back_keyboard
import os
import re
from datetime import datetime, timedelta

router = Router()
logger = standard_logger


# ==========================================
# АДМИН-ПАНЕЛЬ - КОМАНДЫ
# ==========================================

@router.message(Command("configs"))
async def cmd_configs(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только для администратора.")
        delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
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
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только для администратора.")
        delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
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
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только для администратора.")
        delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
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
        import shutil
        shutil.rmtree(user_dir)
        await message.answer(f"✅ Все конфиги пользователя <b>{username}</b> удалены.", parse_mode="HTML")
        audit_logger.info(f"ACTION:CLEAR_USER | ADMIN:{message.from_user.id} | USER:{username}")
    else:
        await message.answer(f"❌ Пользователь <b>{username}</b> не найден.", parse_mode="HTML")


@router.message(Command("clearproxy"))
async def cmd_clearproxy(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        msg = await message.answer("❌ Только для администратора.")
        delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
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


# ==========================================
# БЕССРОЧНЫЙ СТАТУС VPN
# ==========================================

@router.callback_query(F.data == "admin_permanent_menu")
async def admin_permanent_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
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
    
    stats = load_json("bot_data/stats.json", {})
    
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


@router.message(Command("permanent"))
async def cmd_permanent(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Только для администратора.")
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


# ==========================================
# СПИСОК ПРОКСИ (АДМИН)
# ==========================================

@router.callback_query(F.data == "admin_proxy_list")
async def admin_proxy_list(callback: types.CallbackQuery):
    """Список всех прокси (админ)"""
    if callback.from_user.id not in ADMIN_IDS:
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
        reply_markup=get_back_keyboard("menu_admin_main").as_markup()
    )


# ==========================================
# БЕССРОЧНЫЙ СТАТУС ДЛЯ ПРОКСИ
# ==========================================

@router.callback_query(F.data == "admin_permanent_proxy_menu")
async def admin_permanent_proxy_menu(callback: types.CallbackQuery):
    """Меню управления бессрочным статусом прокси"""
    if callback.from_user.id not in ADMIN_IDS:
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


@router.message(Command("permanent_proxy"))
async def cmd_permanent_proxy(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Только для администратора.")
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
