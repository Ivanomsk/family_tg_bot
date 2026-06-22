from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatType
from bot.utils.logger import bot_logger
from bot.keyboards.reply import main_menu_keyboard

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    bot_logger.info(f"Пользователь {user.full_name} (@{user.username}) запустил бота")

    # ЛС: полное меню + кнопки
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            f"👋 Привет, <b>{user.full_name}</b>!\n\n"
            f"Это <b>VPN и Прокси бот для семьи и друзей</b>.\n"
            f"Все конфиги и личные данные отправляются только сюда.\n\n"
            f"⚙️ Твой ID: <code>{user.id}</code>",
            reply_markup=main_menu_keyboard()
        )
        return

    # Общий чат: ТОЛЬКО СПРАВКА. Без кнопок, без личных данных.
    safe_name = user.full_name or user.username or f"Пользователь {user.id}"
    await message.answer(
        f"ℹ️ <b>Справка по боту</b>\n\n"
        f"• Для управления VPN и Прокси напиши мне <b>в личные сообщения</b>.\n"
        f"• Нажми на мою иконку в списке чатов и выбери <b>«Запустить»</b>.\n"
        f"• В ЛС доступны команды: /vpn, /proxy, /start.\n\n"
        f"📌 Все ключи, конфиги и статусы приходят только в ЛС."
    )
