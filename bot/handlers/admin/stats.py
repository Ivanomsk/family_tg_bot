from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatType
from bot.handlers.admin import router, is_admin
from bot.repositories.user_repository import UserRepository
from bot.config import DATA_DIR

stats_router = Router()

user_repo = UserRepository(DATA_DIR)

@stats_router.message(Command("admin_stats"))
async def cmd_admin_stats(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав администратора.")
        return
    
    users = await user_repo.get_all()
    total = len(users)
    active = sum(1 for u in users if u.is_active and not u.is_expired())
    expired = sum(1 for u in users if u.is_active and u.is_expired())
    revoked = sum(1 for u in users if not u.is_active)
    
    response = (
        f"📊 <b>Статистика VPN</b>\n\n"
        f"👤 Всего пользователей: {total}\n"
        f"✅ Активных: {active}\n"
        f"⏰ Истекших: {expired}\n"
        f"🚫 Отозванных: {revoked}"
    )
    
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(response)
    else:
        await message.answer("✅ Результат отправлен в личные сообщения.")
        await message.bot.send_message(message.from_user.id, response)
