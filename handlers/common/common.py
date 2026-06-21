import os
import re

from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import VPN_DIR
from utils.auto_delete import delete_temp
from utils.logger import standard_logger

logger = standard_logger


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
        files = [f for f in os.listdir(user_dir) if f.endswith(".vpn")]
        logger.info(
            f"📁 Сканируем папку {user_dir}: найдено {len(files)} файлов: {files}"
        )
        return sorted(files)

    except Exception as e:
        logger.error(f"Ошибка сканирования папки {user_dir}: {e}")
        return []


async def require_private_chat(
    callback: types.CallbackQuery,
    feature_name: str = "эта функция"
) -> bool:

    if callback.message.chat.type != "private":
        bot_info = await callback.bot.get_me()
        bot_username = bot_info.username

        builder = InlineKeyboardBuilder()
        builder.button(
            text="💬 Открыть чат с ботом",
            url=f"https://t.me/{bot_username}"
        )
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