from pathlib import Path
from typing import List
from bot.models.proxy import ProxyUser
from bot.repositories.base_repository import BaseRepository
from bot.utils.logger import bot_logger

class ProxyRepository(BaseRepository):
    def __init__(self, data_dir: Path):
        super().__init__(data_dir)
        self.filename = "user_proxies.json"

    async def get_all(self) -> List[ProxyUser]:
        data = await self._read_json(self.filename)
        try:
            return [ProxyUser(**item) for item in data]
        except Exception as e:
            bot_logger.error(f"Ошибка парсинга ProxyUser: {e}")
            return []

    async def add_user(self, user: ProxyUser) -> bool:
        users = await self.get_all()
        users = [u for u in users if u.tg_id != user.tg_id]
        users.append(user)
        data = [u.to_dict() for u in users]
        return await self._write_json(self.filename, data)

    async def get_by_tg_id(self, tg_id: int) -> ProxyUser | None:
        users = await self.get_all()
        for u in users:
            if u.tg_id == tg_id:
                return u
        return None
