from aiogram import Router, types, F
from aiogram.filters import Command
from config import ADMIN_IDS, VPN_DIR, BACKUP_DIR
from utils.logger import standard_logger, audit_logger
from database.storage import load_json, save_json
from utils.vpn_manager import load_vpn_db, save_vpn_db, revoke_vpn_config
from handlers.start import get_user_dir
from handlers.main_menu import admin_private_only
from keyboards.inline import get_back_keyboard
import os
import shutil
from datetime import datetime, timedelta

router = Router()
logger = standard_logger


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
        if key_part and not public_key.startswith(key_part):
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
