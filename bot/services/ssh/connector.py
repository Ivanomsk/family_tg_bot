import asyncssh
from pathlib import Path
from bot.config import VPN_SSH_HOST, VPN_SSH_PORT, VPN_SSH_USER, VPN_SSH_KEY_PATH
from bot.utils.logger import bot_logger

class SSHConnector:
    def __init__(self):
        self.host = VPN_SSH_HOST
        self.port = VPN_SSH_PORT
        self.username = VPN_SSH_USER
        self.key_path = Path(VPN_SSH_KEY_PATH)

    async def connect(self):
        try:
            conn = await asyncssh.connect(
                host=self.host,
                port=self.port,
                username=self.username,
                client_keys=[str(self.key_path)],
                known_hosts=None
            )
            return conn
        except Exception as e:
            bot_logger.error(f"Ошибка SSH подключения к {self.host}: {e}")
            return None
