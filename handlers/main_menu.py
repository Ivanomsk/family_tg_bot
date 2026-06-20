from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import ADMIN_IDS
from utils.auto_delete import delete_user, delete_admin, delete_temp
from utils.logger import standard_logger, audit_logger
from utils.stats import update_stats
from keyboards.inline import (
    get_main_menu_keyboard,
    get_back_to_main_menu,
    get_help_main_keyboard,
    get_back_keyboard,
    get_problem_cancel_keyboard,
    get_admin_main_keyboard
)
from states.forms import ProblemReport
import re
from datetime import datetime

router = Router()
logger = standard_logger


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

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
# УНИВЕРСАЛЬНАЯ ПРОВЕРКА ДЛЯ АДМИН-КОМАНД
# ==========================================

async def admin_private_only(message: types.Message) -> bool:
    """
    Проверяет, что команда вызвана админом в ЛС.
    Возвращает True если всё ок, False если нужно прекратить.
    """
    from config import ADMIN_IDS
    from utils.auto_delete import delete_temp
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    # Проверяем, что это админ
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Только для администратора.")
        return False
    
    # Проверяем, что это ЛС
    if message.chat.type != "private":
        bot_info = await message.bot.get_me()
        bot_username = bot_info.username
        builder = InlineKeyboardBuilder()
        builder.button(text="💬 Открыть чат с ботом", url=f"https://t.me/{bot_username}")
        builder.adjust(1)
        msg = await message.answer(
            f"❌ <b>Команда доступна только в личных сообщениях!</b>\n\n"
            f"👉 Нажмите кнопку ниже, чтобы перейти в ЛС:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        delete_temp(message.bot, message.chat.id, msg.message_id, user_id=message.from_user.id, chat_type=message.chat.type)
        return False
    
    return True
