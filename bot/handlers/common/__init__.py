from aiogram import Router
from bot.handlers.common.start import start_router
from bot.handlers.common.feedback import feedback_router

# Главный роутер общих команд
router = Router()
router.include_router(start_router)
router.include_router(feedback_router)
