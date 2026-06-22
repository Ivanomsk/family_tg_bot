from pathlib import Path
from typing import List
from bot.models.vpn import VPNUser
from bot.repositories.base_repository import BaseRepository
from bot.utils.logger import bot_logger

class UserRepository(BaseRepository):
    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        self.filename = "vpn_users.json"

    async def get_all(self) -> List[VPNUser]:
        data = await self._read_json(self.filename)
        try:
            return [VPNUser(**item) for item in data]
        except Exception as e:
            bot_logger.error(f"Ошибка парсинга VPNUser: {e}")
            return []

    async def add_user(self, user: VPNUser) -> bool:
        users = await self.get_all()
        # Удаляем старого пользователя с таким же tg_id, если есть
        users = [u for u in users if u.tg_id != user.tg_id]
        users.append(user)
        data = [u.to_dict() for u in users]
        return await self._write_json(self.filename, data)

    async def get_by_tg_id(self, tg_id: int) -> VPNUser | None:
        users = await self.get_all()
        for u in users:
            if u.tg_id == tg_id:
                return u
        return None
