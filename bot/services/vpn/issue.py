from datetime import datetime, timedelta
from bot.models.vpn import VPNUser
from bot.services.vpn.core import VPNCoreService
from bot.config import VPN_EXPIRY_DAYS
from bot.utils.logger import bot_logger

class VPNIssueService:
    def __init__(self, core_service: VPNCoreService):
        self.core = core_service
        self.user_repo = core_service.user_repo

    async def issue_vpn(self, tg_id: int, username: str, days: int = VPN_EXPIRY_DAYS) -> bool:
        user = await self.core.get_user(tg_id)
        now = datetime.now()
        new_expiry = now + timedelta(days=days)
        
        if user and not user.is_expired():
            new_expiry = user.expiry_date + timedelta(days=days)
            bot_logger.info(f"Продлеваем VPN для {username} (tg_id={tg_id}) до {new_expiry}")
        else:
            bot_logger.info(f"Выдаём новый VPN для {username} (tg_id={tg_id}) до {new_expiry}")
        
        updated_user = VPNUser(
            tg_id=tg_id,
            username=username,
            first_name=username,
            expiry_date=new_expiry,
            is_active=True
        )
        return await self.user_repo.add_user(updated_user)
