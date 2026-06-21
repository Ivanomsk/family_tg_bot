from aiogram import Router

from .menu import router as menu_router
from .list import router as list_router
from .issue import router as issue_router
from .revoke import router as revoke_router
from .test import router as test_router

router = Router()

router.include_router(menu_router)
router.include_router(list_router)
router.include_router(issue_router)
router.include_router(revoke_router)
router.include_router(test_router)
