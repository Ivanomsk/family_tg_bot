from aiogram import Router
from aiogram.types import ErrorEvent
from config import ADMIN_IDS
import logging

router = Router()
logger = logging.getLogger(__name__)

@router.errors()
async def error_handler(event: ErrorEvent):
    exc = event.exception
    logger.error(f"🚨 Ошибка: {exc}", exc_info=True)
    for admin_id in ADMIN_IDS:
        try:
            user = event.update.effective_user
            uid = user.id if user else "Unknown"
            msg = event.update.message
            txt = msg.text if msg and msg.text else "Button/Inline"
            report = f"🚨 ОШИБКА БОТА\nUser: {uid}\nAction: {txt}\nError: {exc}"
            await event.bot.send_message(admin_id, report, parse_mode=None)
        except Exception:
            pass