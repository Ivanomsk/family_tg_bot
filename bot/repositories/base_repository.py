import json
import aiofiles
from pathlib import Path
from bot.utils.logger import bot_logger

class BaseRepository:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def _read_json(self, filename: str) -> list | dict:
        path = self.data_dir / filename
        try:
            async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                return json.loads(await f.read())
        except FileNotFoundError:
            bot_logger.warning(f"Файл {filename} не найден, создаём пустой.")
            return [] if filename.endswith('s.json') else {}
        except Exception as e:
            bot_logger.error(f"Ошибка чтения {filename}: {e}")
            return []

    async def _write_json(self, filename: str, data: list | dict) -> bool:
        path = self.data_dir / filename
        try:
            async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
            return True
        except Exception as e:
            bot_logger.error(f"Ошибка записи {filename}: {e}")
            return False
