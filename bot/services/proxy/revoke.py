from bot.models.proxy import ProxyUser
from bot.services.proxy.core import ProxyCoreService
from bot.utils.logger import bot_logger

class ProxyRevokeService:
    def __init__(self, core_service: ProxyCoreService):
        self.core = core_service
        self.proxy_repo = core_service.proxy_repo

    async def revoke_proxy(self, tg_id: int) -> bool:
        user = await self.core.get_user(tg_id)
        if not user:
            return False
        revoked_user = ProxyUser(
            tg_id=tg_id,
            username=user.username,
            expiry_date=user.expiry_date,
            is_active=False
        )
        bot_logger.info(f"Прокси отозван для tg_id={tg_id}")
        return await self.proxy_repo.add_user(revoked_user)
