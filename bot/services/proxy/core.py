from typing import Optional
from bot.models.proxy import ProxyUser
from bot.repositories.proxy_repository import ProxyRepository

class ProxyCoreService:
    def __init__(self, proxy_repo: ProxyRepository):
        self.proxy_repo = proxy_repo

    async def get_user(self, tg_id: int) -> Optional[ProxyUser]:
        return await self.proxy_repo.get_by_tg_id(tg_id)
