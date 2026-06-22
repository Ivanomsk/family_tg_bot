from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from bot.handlers.admin import router, is_admin
from bot.dispatcher import bot
from bot.repositories.feedback_repository import FeedbackRepository
from bot.config import DATA_DIR
from bot.utils.logger import bot_logger

reply_router = Router()
feedback_repo = FeedbackRepository(DATA_DIR)

@reply_router.message(Command("reply"))
async def cmd_reply(message: Message):
    if not await is_admin(message.from_user.id):
        return
    
    args = message.text.split(maxsplit=3)
    if len(args) < 4:
        await message.answer("❌ Использование: /reply <ticket_id> <user_id> <текст>")
        return
    
    ticket_id = args[1]
    user_id = int(args[2])
    reply_text = args[3]
    
    ticket = await feedback_repo.get_ticket_by_id(ticket_id)
    if not ticket or ticket.status != "open":
        await message.answer("❌ Тикет не найден или уже закрыт.")
        return
    
    await feedback_repo.add_message(ticket_id, user_id, reply_text)
    await bot.send_message(user_id, f"📩 <b>Ответ администратора</b>\n\n{reply_text}")
    await message.answer(f"✅ Ответ отправлен пользователю {user_id}.")
    bot_logger.info(f"Админ {message.from_user.id} ответил пользователю {user_id}")
