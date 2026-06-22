from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.handlers.admin import router, is_admin
from bot.repositories.feedback_repository import FeedbackRepository
from bot.config import DATA_DIR

close_router = Router()
feedback_repo = FeedbackRepository(DATA_DIR)

@close_router.message(Command("close"))
async def cmd_close(message: Message):
    if not await is_admin(message.from_user.id):
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /close <ticket_id>")
        return
    
    ticket_id = args[1]
    if await feedback_repo.close_ticket(ticket_id):
        await message.answer(f"✅ Тикет #{ticket_id[:8]} закрыт.")
    else:
        await message.answer("❌ Тикет не найден.")
