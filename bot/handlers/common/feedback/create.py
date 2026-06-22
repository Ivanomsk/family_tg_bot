from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, ChatType
from aiogram.enums import ChatType
from aiogram.fsm.context import FSMContext
from bot.states.forms import FeedbackForm
from bot.utils.logger import bot_logger
from bot.config import ADMIN_IDS, DATA_DIR
from bot.dispatcher import bot
from bot.repositories.feedback_repository import FeedbackRepository

feedback_router = Router()
feedback_repo = FeedbackRepository(DATA_DIR)

@feedback_router.message(lambda message: message.text == "📩 Сообщить о проблеме")
async def cmd_feedback_button(message: Message, state: FSMContext):
    if message.chat.type != ChatType.PRIVATE:
        await message.answer("ℹ️ Эта функция доступна только в личных сообщениях.")
        return
    
    active = await feedback_repo.get_active_ticket(message.from_user.id)
    if active:
        await message.answer(
            f"ℹ️ У вас уже есть активный тикет #{active.ticket_id[:8]}.\n"
            f"Вы можете продолжить диалог, написав сообщение."
        )
        await state.set_state(FeedbackForm.waiting_for_message)
        return

    ticket_id = await feedback_repo.create_ticket(message.from_user.id, message.from_user.username or "User")
    await message.answer(
        f"📩 Тикет #{ticket_id[:8]} создан.\n"
        f"Пожалуйста, опишите вашу проблему или вопрос одним сообщением.\n"
        f"Администратор получит ваше сообщение и ответит вам."
    )
    await state.set_state(FeedbackForm.waiting_for_message)

@feedback_router.message(Command("feedback"))
async def cmd_feedback_command(message: Message, state: FSMContext):
    if message.chat.type != ChatType.PRIVATE:
        await message.answer("ℹ️ Эта функция доступна только в личных сообщениях.")
        return
    
    await message.answer(
        "📩 Пожалуйста, опишите вашу проблему или вопрос одним сообщением.\n"
        "Администратор получит ваше сообщение и ответит вам в ближайшее время."
    )
    await state.set_state(FeedbackForm.waiting_for_message)

@feedback_router.message(FeedbackForm.waiting_for_message)
async def process_feedback_message(message: Message, state: FSMContext):
    user = message.from_user
    ticket = await feedback_repo.get_active_ticket(user.id)
    
    if not ticket:
        ticket_id = await feedback_repo.create_ticket(user.id, user.username or "User")
        await feedback_repo.add_message(ticket_id, user.id, message.text or "без текста")
        await message.answer("✅ Сообщение отправлено (тикет создан).")
    else:
        await feedback_repo.add_message(ticket.ticket_id, user.id, message.text or "без текста")
        await message.answer("✅ Сообщение добавлено к тикету.")
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"📩 <b>Новое сообщение</b> (тикет #{ticket.ticket_id[:8]})\n"
                f"👤 От: {user.full_name} (@{user.username})\n"
                f"🆔 ID: {user.id}\n"
                f"📝 Сообщение:\n<code>{message.text}</code>"
            )
        except Exception as e:
            bot_logger.error(f"Не удалось отправить админу {admin_id}: {e}")
    
    await state.set_state(FeedbackForm.waiting_for_message)
