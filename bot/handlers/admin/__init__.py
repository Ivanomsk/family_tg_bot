from aiogram import Router
from bot.handlers.admin.issue import issue_router
from bot.handlers.admin.revoke import revoke_router
from bot.handlers.admin.stats import stats_router
from bot.handlers.admin.reply import reply_router
from bot.handlers.admin.close import close_router
from bot.config import ADMIN_IDS

# Главный роутер администратора
router = Router()
router.include_router(issue_router)
router.include_router(revoke_router)
router.include_router(stats_router)
router.include_router(reply_router)
router.include_router(close_router)

async def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
