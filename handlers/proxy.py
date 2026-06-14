from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import datetime
import urllib.parse
import logging

from config import ADMIN_IDS, USER_PROXIES_FILE, PROXY_EXPIRY_DAYS, is_allowed
from utils.auto_delete import schedule_delete, delete_temp, delete_user, delete_proxy_card, delete_admin
from utils.stats import update_stats
from utils.expiry import get_proxy_age
from utils.notifications import send_proxy_expiry_notification
from utils.rate_limit import is_rate_limited
from database.storage import load_json, save_json
from states.forms import ProxyRequest
from keyboards.inline import (
    get_admin_proxy_request_keyboard as get_proxy_request_keyboard,
    get_proxy_list_keyboard_compat as get_proxy_list_keyboard,
    get_proxy_card_keyboard
)

router = Router()
logger = logging.getLogger(__name__)

proxy_pending_admin = {}
my_proxy_cache = {}

def format_proxy_card(name: str, server: str, port: int, secret: str) -> str:
    return (
        f"🔒 <b>{name}</b>\n\n"
        f"🌐 <b>Сервер:</b> {server}\n"
        f"🔌 <b>Порт:</b> {port}\n"
        f"🔑 <b>Секрет:</b> <code>{secret}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 <b>Как подключить вручную:</b>\n"
        f"1. Настройки → Данные и память → Прокси\n"
        f"2. Добавить прокси → MTProto\n"
        f"3. Ввести данные выше\n"
        f"4. Нажать Готово\n\n"
        f"💡 <i>Сохрани секрет в заметках!</i>"
    )

def format_proxy_card_with_button(name: str, server: str, port: int, secret: str):
    tg_link = f"tg://proxy?server={server}&port={port}&secret={secret}"
    text = (
        f"🔒 <b>{name}</b>\n\n"
        f"🌐 <b>Сервер:</b> {server}\n"
        f"🔌 <b>Порт:</b> {port}\n"
        f"🔑 <b>Секрет:</b> <code>{secret}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📋 <b>Как подключить вручную:</b>\n"
        f"1. Настройки → Данные и память → Прокси\n"
        f"2. Добавить прокси → MTProto\n"
        f"3. Ввести данные выше\n"
        f"4. Нажать Готово\n\n"
        f"💡 <i>Сохрани секрет в заметках!</i>"
    )
    return text, tg_link

@router.message(Command("request_proxy"))
async def cmd_request_proxy(message: types.Message):
    # 🔒 ПРОВЕРКА: только в ЛС!
    if message.chat.type != "private":
        msg = await message.answer(
            "🔐 Запрос прокси работает только в личных сообщениях!\n\n"
            f"👉 Напиши боту в ЛС: t.me/{(await message.bot.get_me()).username}",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    is_limited, retry_after = is_rate_limited(message.from_user.id, "request_proxy")
    if is_limited:
        msg = await message.answer(
            f"⏳ Слишком много запросов. Попробуйте через {retry_after} сек.",
            parse_mode="HTML"
        )
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    user_id = message.from_user.id
    username = message.from_user.username or f"ID:{user_id}"
    update_stats(message.from_user, "proxy_request")
    builder = get_proxy_request_keyboard(user_id)

    request_msg = (
        f"🛰 <b>ЗАПРОС НОВОГО ПРОКСИ</b>\n\n"
        f"👤 @{username}\n📱 ID: {user_id}\n\n"
        f"Ждёт персональный прокси-ключ!"
    )

    for admin_id in ADMIN_IDS:
        try:
            msg = await message.bot.send_message(
                admin_id, request_msg, reply_markup=builder.as_markup(), parse_mode="HTML"
            )
            proxy_pending_admin[user_id] = {"msg_id": msg.message_id, "chat_id": msg.chat.id, "admin_id": admin_id}
        except Exception as e:
            logger.error(f"❌ Ошибка отправки запроса прокси админу {admin_id}: {e}")

    msg = await message.answer("✅ Запрос на прокси отправлен админу!\nОжидай ответа...", parse_mode="HTML")
    delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.callback_query(F.data.startswith("proxy_req_issue_"))
async def proxy_admin_start_issue(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    user_id = int(callback.data.split("_")[-1])
    if user_id in proxy_pending_admin:
        proxy_pending_admin[user_id]["admin_id"] = callback.from_user.id

    await state.set_state(ProxyRequest.waiting_for_name)
    msg = await callback.message.answer(
        f"📝 <b>Ввод данных прокси для пользователя ID {user_id}</b>\n\n"
        f"<b>Шаг 1:</b> Напиши название прокси\n(например: Основной, Резервный)\n\n"
        f"Или нажми /cancel для отмены",
        parse_mode="HTML"
    )
    delete_admin(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=callback.from_user.id, chat_type=callback.message.chat.type)
    await callback.answer()

@router.message(ProxyRequest.waiting_for_name, F.text)
async def proxy_admin_get_name(message: types.Message, state: FSMContext):
    admin_id = message.from_user.id
    target_user_id = None
    for uid, data in proxy_pending_admin.items():
        if data.get("admin_id") == admin_id:
            target_user_id = uid
            break

    if not target_user_id:
        msg = await message.answer("❌ Нет активного запроса прокси.")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        await state.clear()
        return

    proxy_name = message.text.strip()
    proxy_pending_admin[target_user_id]["proxy_name"] = proxy_name
    await state.set_state(ProxyRequest.waiting_for_data)

    msg = await message.answer(
        f"📝 <b>Название: {proxy_name}</b>\n\n"
        f"<b>Шаг 2:</b> Введи данные прокси\n\n"
        f"<b>Формат 1:</b> ссылка tg://proxy?server=...&port=...&secret=...\n"
        f"<b>Формат 2:</b> server|port|secret\n\n"
        f"Или нажми /cancel для отмены",
        parse_mode="HTML"
    )
    delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.message(ProxyRequest.waiting_for_data, F.text)
async def proxy_admin_save_data(message: types.Message, state: FSMContext):
    text = message.text.strip()
    admin_id = message.from_user.id
    target_user_id = None
    for uid, data in proxy_pending_admin.items():
        if data.get("admin_id") == admin_id:
            target_user_id = uid
            break

    if not target_user_id:
        msg = await message.answer("❌ Нет активного запроса прокси.")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        await state.clear()
        return

    try:
        proxy_data = {}
        if text.startswith("tg://"):
            parsed = urllib.parse.urlparse(text)
            params = urllib.parse.parse_qs(parsed.query)
            proxy_data = {"server": params.get("server", [""])[0], "port": int(params.get("port", [0])[0]), "secret": params.get("secret", [""])[0]}
        elif "|" in text:
            parts = text.split("|")
            if len(parts) != 3:
                msg = await message.answer("❌ Неверный формат. Нужно: server|port|secret")
                delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
                return
            proxy_data = {"server": parts[0].strip(), "port": int(parts[1].strip()), "secret": parts[2].strip()}
        else:
            msg = await message.answer("❌ Неверный формат.\nИспользуй ссылку или server|port|secret", parse_mode="HTML")
            delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
            return

        proxy_name = proxy_pending_admin[target_user_id].get("proxy_name", "Прокси")
        user_proxies = load_json(USER_PROXIES_FILE, {})
        if str(target_user_id) not in user_proxies:
            user_proxies[str(target_user_id)] = {"proxies": []}

        user_proxies[str(target_user_id)]["proxies"].append({
            "name": proxy_name, "server": proxy_data["server"], "port": proxy_data["port"],
            "secret": proxy_data["secret"], "issued_at": datetime.datetime.now().isoformat(), "issued_by": admin_id
        })
        save_json(USER_PROXIES_FILE, user_proxies)

        try:
            target_user = await message.bot.get_chat(target_user_id)
            target_username = target_user.username or f"ID:{target_user_id}"
        except Exception:
            target_username = f"ID:{target_user_id}"

        tg_link = f"tg://proxy?server={proxy_data['server']}&port={proxy_data['port']}&secret={proxy_data['secret']}"
        card_text, _ = format_proxy_card_with_button(proxy_name, proxy_data["server"], proxy_data["port"], proxy_data["secret"])
        
        # ✅ КАРТОЧКА ПРОКСИ: 5 минут
        msg_card = await message.bot.send_message(
            target_user_id, card_text, reply_markup=get_proxy_card_keyboard(tg_link).as_markup(),
            parse_mode="HTML", disable_web_page_preview=False
        )
        delete_proxy_card(message.bot, target_user_id, msg_card.message_id, user_id=target_user_id, chat_type="private")

        msg = await message.answer(f"✅ Прокси <b>{proxy_name}</b> добавлен для @{target_username}!", parse_mode="HTML")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

        # ✅ БЕЗОПАСНАЯ ПРОВЕРКА наличия chat_id и msg_id
        info = proxy_pending_admin.get(target_user_id)
        if info:
            chat_id = info.get("chat_id")
            msg_id = info.get("msg_id")
            
            if chat_id and msg_id:
                try:
                    await message.bot.edit_message_text(
                        chat_id=chat_id, 
                        message_id=msg_id,
                        text=f"✅ <b>Прокси выдан!</b>\n\n👤 Пользователь ID: {target_user_id}\n📝 Название: {proxy_name}\n📤 Отправлено: {datetime.datetime.now().strftime('%H:%M:%S')}",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.warning(f"Не удалось отредактировать сообщение: {e}")
            else:
                logger.debug(f"Нет chat_id/msg_id для пользователя {target_user_id}, пропускаем редактирование")
            
            del proxy_pending_admin[target_user_id]

        logger.info(f"📤 Прокси '{proxy_name}' выдан пользователю ID {target_user_id} админом {admin_id}")

    except Exception as e:
        msg = await message.answer(f"❌ Ошибка: {e}")
        delete_admin(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

    await state.clear()

@router.callback_query(F.data.startswith("proxy_req_reject_"))
async def proxy_admin_reject(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("❌ Только админ", show_alert=True)
        return
    user_id = int(callback.data.split("_")[-1])
    try:
        msg = await callback.message.bot.send_message(user_id, "📄 <b>Запрос на прокси отклонён</b>\n\nЕсли считаешь это ошибкой — напиши админу.", parse_mode="HTML")
        delete_user(callback.message.bot, user_id, msg.message_id, user_id=user_id, chat_type="private")
        await callback.message.edit_text(f"❌ <b>Запрос отклонён</b>\n🕐 Время: {datetime.datetime.now().strftime('%H:%M:%S')}", parse_mode="HTML")
    except Exception:
        pass
    if user_id in proxy_pending_admin:
        del proxy_pending_admin[user_id]
    await callback.answer()

@router.message(Command("my_proxy"))
async def cmd_my_proxy(message: types.Message):
    # 🔒 ПРОВЕРКА: только в ЛС!
    if message.chat.type != "private":
        msg = await message.answer(
            "🔐 Просмотр прокси работает только в личных сообщениях!\n\n"
            f"👉 Напиши боту в ЛС: t.me/{(await message.bot.get_me()).username}",
            parse_mode="HTML",
            disable_web_page_preview=True
        )
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    is_limited, retry_after = is_rate_limited(message.from_user.id, "my_proxy")
    if is_limited:
        msg = await message.answer(f"⏳ Слишком много запросов. Попробуйте через {retry_after} сек.", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    user_id = message.from_user.id
    user_proxies = load_json(USER_PROXIES_FILE, {})

    if str(user_id) not in user_proxies or "proxies" not in user_proxies[str(user_id)] or not user_proxies[str(user_id)]["proxies"]:
        msg = await message.answer("❌ У тебя пока нет прокси.\n\nИспользуй /request_proxy чтобы запросить.", parse_mode="HTML")
        delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return

    proxies = user_proxies[str(user_id)]["proxies"]
    my_proxy_cache[user_id] = proxies

    expired_proxies, expiring_proxies = [], []
    for proxy in proxies:
        age = get_proxy_age(user_id, proxy["name"])
        if age["status"] == "expired":
            expired_proxies.append({"name": proxy["name"], "days_expired": abs(age["days_left"])})
        elif age["status"] == "expiring_soon":
            expiring_proxies.append({"name": proxy["name"], "days_left": age["days_left"]})

    if expired_proxies or expiring_proxies:
        username = message.from_user.username or f"ID:{user_id}"
        await send_proxy_expiry_notification(message.bot, user_id, username, expired_proxies, expiring_proxies)

    builder = InlineKeyboardBuilder()
    for i, proxy in enumerate(proxies):
        age = get_proxy_age(user_id, proxy["name"])
        if age["status"] == "expired":
            button_text = f"❌ {proxy['name']} (истёк)"
        elif age["status"] == "expiring_soon":
            button_text = f"⚠️ {proxy['name']} ({age['days_left']} дн.)"
        else:
            button_text = f"🔹 {proxy['name']}"
        builder.button(text=button_text, callback_data=f"proxy_show_{i}")
    builder.adjust(1)

    text = f"👁 <b>Твои прокси ({len(proxies)} шт.):</b>\n\n"
    if expired_proxies or expiring_proxies:
        text += "━━━━━━━━━━━━━━━━━━━━\n"
        for proxy in expired_proxies: text += f"❌ <b>{proxy['name']}</b> — ИСТЁК {proxy['days_expired']} дн. назад!\n"
        for proxy in expiring_proxies: text += f"⚠️ <b>{proxy['name']}</b> — истекает через {proxy['days_left']} дн.\n"
        text += "━━━━━━━━━━━━━━━━━━━━\n\n💡 Если прокси истёк — запроси новый через /request_proxy\n\n"
    text += "Выбери нужный:"

    msg = await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    delete_user(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)

@router.callback_query(F.data.startswith("proxy_show_"))
async def process_proxy_show(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    proxies = my_proxy_cache.get(user_id)

    if not proxies:
        msg = await callback.message.answer("❌ Данные прокси не найдены. Используй /my_proxy снова.", parse_mode="HTML")
        delete_user(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=user_id, chat_type=callback.message.chat.type)
        return

    try:
        index = int(callback.data.split("_")[-1])
        proxy = proxies[index]
    except (IndexError, ValueError):
        msg = await callback.message.answer("❌ Прокси не найден.", parse_mode="HTML")
        delete_user(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=user_id, chat_type=callback.message.chat.type)
        return

    card_text, tg_link = format_proxy_card_with_button(proxy["name"], proxy["server"], proxy["port"], proxy["secret"])
    builder = get_proxy_card_keyboard(tg_link)

    # ✅ КАРТОЧКА ПРОКСИ: 5 минут
    msg = await callback.message.answer(card_text, reply_markup=builder.as_markup(), parse_mode="HTML", disable_web_page_preview=False)
    delete_proxy_card(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=user_id, chat_type=callback.message.chat.type)

@router.callback_query(F.data == "proxy_list")
async def process_proxy_list(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    proxies = my_proxy_cache.get(user_id)

    if not proxies:
        msg = await callback.message.answer("📄 Данные прокси не найдены. Используй /my_proxy снова.", parse_mode="HTML")
        delete_user(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=user_id, chat_type=callback.message.chat.type)
        return

    builder = get_proxy_list_keyboard(proxies)
    msg = await callback.message.answer(f"👁 <b>Твои прокси ({len(proxies)} шт.):</b>\n\n📝 Выбери нужный:", reply_markup=builder.as_markup(), parse_mode="HTML")
    delete_user(callback.message.bot, callback.message.chat.id, msg.message_id, user_id=user_id, chat_type=callback.message.chat.type)