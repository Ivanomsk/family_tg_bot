from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatType
from bot.handlers.admin import router, is_admin
from bot.services.vpn.revoke import VPNRevokeService
from bot.services.vpn.core import VPNCoreService
from bot.repositories.user_repository import UserRepository
from bot.config import DATA_DIR
from bot.utils.logger import bot_logger
from bot.dispatcher import bot
from bot.services.notification_service import NotificationService

revoke_router = Router()

user_repo = UserRepository(DATA_DIR)
core = VPNCoreService(user_repo)
revoke_service = VPNRevokeService(core)
notification_service = NotificationService(bot, None)

@revoke_router.message(Command("admin_revoke"))
async def cmd_admin_revoke(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /admin_revoke <tg_id>")
        return
    
    try:
        tg_id = int(args[1])
    except ValueError:
        await message.answer("❌ ID должен быть числом.")
        return
    
    success = await revoke_service.revoke_vpn(tg_id)
    if success:
        await message.answer(f"✅ VPN отозван для пользователя {tg_id}.")
        await notification_service.notify_revoke(tg_id, "VPN")
        bot_logger.info(f"Админ {message.from_user.id} отозвал VPN для {tg_id}")
    else:
        await message.answer("❌ Пользователь не найден или ошибка при отзыве.")
