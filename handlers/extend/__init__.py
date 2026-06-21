from aiogram import Router

from .requests import router as requests_router
from .configs import router as configs_router

router = Router()

router.include_router(requests_router)
router.include_router(configs_router)