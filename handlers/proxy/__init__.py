from .menu import router as menu_router
from .select import router as select_router
from .request import router as request_router
from .extend import router as extend_router
from .issue import router as issue_router
from .reject import router as reject_router

from aiogram import Router

router = Router()

router.include_router(menu_router)
router.include_router(select_router)
router.include_router(request_router)
router.include_router(extend_router)
router.include_router(issue_router)
router.include_router(reject_router)