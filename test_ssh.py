import asyncio
import asyncssh
from pathlib import Path

# Настройки из твоего .env
SSH_HOST = "89.125.188.152"
SSH_PORT = 22
SSH_USER = "root"
SSH_KEY_PATH = "/opt/durdom-bot/ssh_keys/durdom_vpn_key"

async def test_connection():
    print(f"🚀 Пытаемся подключиться к {SSH_HOST}:{SSH_PORT}...")
    
    try:
        # Передаём путь к файлу, а не его содержимое
        conn = await asyncssh.connect(
            host=SSH_HOST,
            port=SSH_PORT,
            username=SSH_USER,
            client_keys=[SSH_KEY_PATH],  # <-- исправлено!
            known_hosts=None
        )
        
        print("✅ SSH-подключение успешно установлено!")
        
        result = await conn.run("echo 'SSH работает!'")
        print(f"📩 Ответ сервера: {result.stdout.strip()}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка SSH-подключения: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_connection())
