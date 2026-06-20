from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import ADMIN_IDS, USER_PROXIES_FILE
from utils.logger import standard_logger, audit_logger
from database.storage import load_json, save_json
from keyboards.inline import (
    get_proxy_main_keyboard,
    get_proxy_list_keyboard,
    get_proxy_empty_keyboard,
    get_proxy_request_keyboard,
    get_back_keyboard
)
from states.forms import ProxyRequest, ProxyExtend
from handlers.main_menu import require_private_chat
import urllib.parse
from datetime import datetime, timedelta

router = Router()
logger = standard_logger


# ==========================================
# МЕНЮ ПРОКСИ
# ==========================================

@router.callback_query(F.data == "menu_proxy_main")
async def menu_proxy_main(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "🛰 <b>Управление прокси</b>\n\nВыберите действие:",
        parse_mode="HTML",
        reply_markup=get_proxy_main_keyboard().as_markup()
    )


@router.callback_query(F.data == "menu_proxy")
async def menu_proxy(callback: types.CallbackQuery):
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


# ==========================================
# ВЫБОР ПРОКСИ (КАРТОЧКА)
# ==========================================

@router.callback_query(F.data.startswith("proxy_select_"))
async def proxy_select(callback: types.CallbackQuery):
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
    
    username = callback.from_user.username or f"ID:{user_id}"
    tg_link = f"tg://proxy?server={proxy['server']}&port={proxy['port']}&secret={proxy['secret']}"
    
    issued_at_raw = proxy.get('issued_at', 'не указана')
    if issued_at_raw != 'не указана':
        try:
            issued_dt = datetime.fromisoformat(issued_at_raw)
            issued_at = issued_dt.strftime('%d.%m.%Y %H:%M')
        except:
            issued_at = issued_at_raw
    else:
        issued_at = 'не указана'
    
    is_permanent = proxy.get('permanent', False)
    
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
    
    buttons = []
    
    if not is_expired or is_permanent:
        buttons.append([InlineKeyboardButton(
            text="📱 Подключить в Telegram",
            url=tg_link
        )])
    
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


# ==========================================
# ЗАПРОС НОВОГО ПРОКСИ
# ==========================================

@router.callback_query(F.data == "proxy_request")
async def proxy_request(callback: types.CallbackQuery):
    if not await require_private_chat(callback, "запрос прокси"):
        return
    
    await callback.answer()
    
    user = callback.from_user
    username = user.username or f"ID:{user.id}"
    
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
# ПРОДЛЕНИЕ ПРОКСИ
# ==========================================

@router.callback_query(F.data.startswith("proxy_extend_"))
async def proxy_extend_request(callback: types.CallbackQuery):
    if not await require_private_chat(callback, "запрос продления"):
        return
    
    await callback.answer()
    
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        user_id = int(parts[1])
        proxy_index = int(parts[2])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    if callback.from_user.id != user_id:
        await callback.answer("⛔ Это не ваш прокси!", show_alert=True)
        return
    
    user_proxies = load_json(USER_PROXIES_FILE, {})
    proxies = user_proxies.get(str(user_id), {}).get("proxies", [])
    
    if proxy_index >= len(proxies):
        await callback.answer("❌ Прокси не найден", show_alert=True)
        return
    
    proxy = proxies[proxy_index]
    username = callback.from_user.username or f"ID:{user_id}"
    user_mention = f"@{username}" if callback.from_user.username else f"ID:{user_id}"
    
    admin_text = (
        f"🔄 <b>Запрос на продление прокси</b>\n\n"
        f"👤 <b>Пользователь:</b> {user_mention}\n"
        f"📁 <b>Имя:</b> {proxy['name']}\n"
        f"🌐 <b>Сервер:</b> {proxy['server']}\n"
        f"📅 <b>Выдан:</b> {proxy.get('issued_at', 'не указана')}\n\n"
        f"Действия:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить продление",
                callback_data=f"proxy_approve_extend_{user_id}_{proxy_index}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"proxy_reject_extend_{user_id}_{proxy_index}"
            )
        ]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                admin_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить запрос админу {admin_id}: {e}")
    
    await callback.answer("✅ Запрос на продление отправлен администратору!")
    await callback.message.edit_text(
        "🔄 <b>Запрос на продление отправлен!</b>\n\n"
        "Администратор рассмотрит ваш запрос в ближайшее время.\n"
        "Вы получите уведомление о решении.",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_proxy").as_markup()
    )
    
    audit_logger.info(
        f"ACTION:PROXY_EXTEND_REQUEST | USER:{user_id} | "
        f"PROXY:{proxy['name']} | INDEX:{proxy_index}"
    )


@router.callback_query(F.data.startswith("proxy_approve_extend_"))
async def proxy_approve_extend(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        target_user_id = int(parts[2])
        proxy_index = int(parts[3])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_proxies = load_json(USER_PROXIES_FILE, {})
    proxies = user_proxies.get(str(target_user_id), {}).get("proxies", [])
    
    if proxy_index >= len(proxies):
        await callback.answer("❌ Прокси не найден", show_alert=True)
        return
    
    proxies[proxy_index]['issued_at'] = datetime.now().isoformat()
    user_proxies[str(target_user_id)]["proxies"] = proxies
    save_json(USER_PROXIES_FILE, user_proxies)
    
    try:
        await callback.bot.send_message(
            target_user_id,
            f"✅ <b>Ваш запрос на продление прокси одобрен!</b>\n\n"
            f"📁 <b>Прокси:</b> {proxies[proxy_index]['name']}\n"
            f"📅 <b>Новая дата выдачи:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"💡 Прокси продлён на 30 дней.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {target_user_id}: {e}")
    
    await callback.answer("✅ Прокси продлён на 30 дней!")
    await callback.message.edit_text(
        f"✅ <b>Продление одобрено!</b>\n\n"
        f"👤 Пользователь получил уведомление.\n"
        f"📁 Прокси: {proxies[proxy_index]['name']}",
        parse_mode="HTML"
    )
    
    audit_logger.info(
        f"ACTION:PROXY_APPROVE_EXTEND | ADMIN:{user_id} | "
        f"USER:{target_user_id} | PROXY:{proxies[proxy_index]['name']}"
    )


@router.callback_query(F.data.startswith("proxy_reject_extend_"))
async def proxy_reject_extend(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        target_user_id = int(parts[2])
        proxy_index = int(parts[3])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_proxies = load_json(USER_PROXIES_FILE, {})
    proxies = user_proxies.get(str(target_user_id), {}).get("proxies", [])
    proxy_name = proxies[proxy_index]['name'] if proxy_index < len(proxies) else "неизвестный"
    
    try:
        await callback.bot.send_message(
            target_user_id,
            f"❌ <b>Ваш запрос на продление прокси отклонён</b>\n\n"
            f"Администратор отклонил ваш запрос.\n"
            f"Если у вас есть вопросы — обратитесь к администратору.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {target_user_id}: {e}")
    
    await callback.answer("❌ Запрос отклонен")
    await callback.message.edit_text(
        f"❌ <b>Запрос отклонен</b>\n\n"
        f"👤 Пользователь получил уведомление об отказе.\n"
        f"📁 Прокси: {proxy_name}",
        parse_mode="HTML"
    )
    
    audit_logger.info(
        f"ACTION:PROXY_REJECT_EXTEND | ADMIN:{user_id} | "
        f"USER:{target_user_id} | PROXY:{proxy_name}"
    )
