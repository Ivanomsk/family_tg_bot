from datetime import datetime, timedelta
from bot.models.proxy import ProxyUser
from bot.services.proxy.core import ProxyCoreService
from bot.config import PROXY_EXPIRY_DAYS
from bot.utils.logger import bot_logger

class ProxyIssueService:
    def __init__(self, core_service: ProxyCoreService):
        self.core = core_service
        self.proxy_repo = core_service.proxy_repo

    async def issue_proxy(self, tg_id: int, username: str, days: int = PROXY_EXPIRY_DAYS) -> bool:
        user = await self.core.get_user(tg_id)
        now = datetime.now()
        new_expiry = now + timedelta(days=days)
        
        if user and not user.is_expired():
            new_expiry = user.expiry_date + timedelta(days=days)
            bot_logger.info(f"Продлеваем Прокси для {username} (tg_id={tg_id}) до {new_expiry}")
        else:
            bot_logger.info(f"Выдаём новый Прокси для {username} (tg_id={tg_id}) до {new_expiry}")
        
        updated_user = ProxyUser(
            tg_id=tg_id,
            username=username,
            expiry_date=new_expiry,
            is_active=True
        )
        return await self.proxy_repo.add_user(updated_user)
