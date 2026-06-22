from datetime import datetime
from bot.repositories.user_repository import UserRepository
from bot.repositories.proxy_repository import ProxyRepository
from bot.utils.logger import bot_logger

class ExpirationService:
    def __init__(self, user_repo: UserRepository, proxy_repo: ProxyRepository):
        self.user_repo = user_repo
        self.proxy_repo = proxy_repo

    async def get_expiring_vpn_users(self, days_threshold: int = 3) -> list:
        """Возвращает список VPN-пользователей, у которых срок истекает через N дней (не бессрочных)"""
        users = await self.user_repo.get_all()
        now = datetime.now()
        expiring = []
        for u in users:
            if u.is_active and not u.is_expired():
                days_left = u.days_left()
                # Если дней > 365 - считаем бессрочным и не уведомляем
                if days_left > 365:
                    continue
                if days_left <= days_threshold:
                    expiring.append(u)
        return expiring

    async def get_expiring_proxy_users(self, days_threshold: int = 3) -> list:
        """Возвращает список Прокси-пользователей, у которых срок истекает через N дней (не бессрочных)"""
        users = await self.proxy_repo.get_all()
        now = datetime.now()
        expiring = []
        for u in users:
            if u.is_active and not u.is_expired():
                days_left = u.days_left()
                if days_left > 365:
                    continue
                if days_left <= days_threshold:
                    expiring.append(u)
        return expiring
