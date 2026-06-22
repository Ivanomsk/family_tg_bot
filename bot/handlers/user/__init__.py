from aiogram import Router
from bot.handlers.user.vpn import vpn_router
from bot.handlers.user.proxy import proxy_router

# Главный роутер пользователей
router = Router()
router.include_router(vpn_router)
router.include_router(proxy_router)
