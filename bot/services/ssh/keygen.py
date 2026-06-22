import subprocess
from bot.utils.logger import bot_logger

class SSHKeyGen:
    @staticmethod
    def generate_wg_keys() -> tuple[str, str]:
        try:
            private_key = subprocess.run(["wg", "genkey"], capture_output=True, text=True).stdout.strip()
            if not private_key:
                raise RuntimeError("wg genkey вернул пустой результат.")
            public_key = subprocess.run(["wg", "pubkey"], input=private_key, capture_output=True, text=True).stdout.strip()
            return private_key, public_key
        except Exception as e:
            bot_logger.error(f"Ошибка генерации ключей: {e}")
            raise
