from bot.models.vpn import VPNUser
from bot.services.vpn.core import VPNCoreService
from bot.utils.logger import bot_logger

class VPNRevokeService:
    def __init__(self, core_service: VPNCoreService):
        self.core = core_service
        self.user_repo = core_service.user_repo

    async def revoke_vpn(self, tg_id: int) -> bool:
        user = await self.core.get_user(tg_id)
        if not user:
            return False
        revoked_user = VPNUser(
            tg_id=tg_id,
            username=user.username,
            expiry_date=user.expiry_date,
            is_active=False
        )
        bot_logger.info(f"VPN отозван для tg_id={tg_id}")
        return await self.user_repo.add_user(revoked_user)
