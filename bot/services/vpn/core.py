from typing import Optional
from bot.models.vpn import VPNUser
from bot.repositories.user_repository import UserRepository

class VPNCoreService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def get_user(self, tg_id: int) -> Optional[VPNUser]:
        return await self.user_repo.get_by_tg_id(tg_id)
