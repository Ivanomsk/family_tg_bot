from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatType
from bot.handlers.admin import router, is_admin
from bot.services.vpn.issue import VPNIssueService
from bot.services.vpn.core import VPNCoreService
from bot.repositories.user_repository import UserRepository
from bot.config import DATA_DIR
from bot.utils.logger import bot_logger

issue_router = Router()

user_repo = UserRepository(DATA_DIR)
core = VPNCoreService(user_repo)
issue_service = VPNIssueService(core)

async def send_admin_response(message: Message, response: str):
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(response)
    else:
        await message.answer(f"✅ Результат отправлен в личные сообщения.")
        await message.bot.send_message(message.from_user.id, response)

@issue_router.message(Command("admin_issue"))
async def cmd_admin_issue(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора.")
        return
    
    args = message.text.split()
    if len(args) < 3:
        await send_admin_response(message, "❌ Использование: /admin_issue <tg_id> <дни>\nПример: /admin_issue 123456789 30")
        return
    
    try:
        tg_id = int(args[1])
        days = int(args[2])
    except ValueError:
        await send_admin_response(message, "❌ ID и дни должны быть числами.")
        return
    
    success = await issue_service.issue_vpn(tg_id, f"user_{tg_id}", days)
    if success:
        await send_admin_response(message, f"✅ VPN успешно выдан пользователю {tg_id} на {days} дней.")
        bot_logger.info(f"Админ {message.from_user.id} выдал VPN для {tg_id}")
    else:
        await send_admin_response(message, "❌ Ошибка при выдаче VPN.")
