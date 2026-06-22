from bot.config import DOCKER_CONTAINER, WG_INTERFACE, VPN_SSH_HOST, WG_SERVER_PORT
from bot.utils.logger import bot_logger

class SSHCommands:
    @staticmethod
    async def add_peer(conn, client_public: str, peer_ip: str) -> bool:
        cmd = (
            f"docker exec {DOCKER_CONTAINER} wg set {WG_INTERFACE} "
            f"peer {client_public} allowed-ips {peer_ip}/32"
        )
        try:
            await conn.run(cmd, check=True)
            bot_logger.info(f"Клиент {client_public} добавлен в {WG_INTERFACE} с IP {peer_ip}")
            return True
        except Exception as e:
            bot_logger.error(f"Ошибка выполнения команды на сервере: {e}")
            return False
