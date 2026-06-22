import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from bot.utils.logger import bot_logger
from bot.dispatcher import bot, dp, set_commands_global
from bot.handlers.admin import router as admin_router
from bot.handlers.user import router as user_router
from bot.handlers.common import router as common_router

from bot.repositories.user_repository import UserRepository
from bot.repositories.proxy_repository import ProxyRepository
from bot.services.expiration_service import ExpirationService
from bot.services.notification_service import NotificationService
from bot.services.background_worker import BackgroundScheduler
from bot.config import DATA_DIR

# Подключаем главные роутеры
dp.include_router(admin_router)
dp.include_router(user_router)
dp.include_router(common_router)

async def main():
    bot_logger.info("Бот запускается...")
    await set_commands_global()
    
    # Инициализируем уведомления
    user_repo = UserRepository(DATA_DIR)
    proxy_repo = ProxyRepository(DATA_DIR)
    exp_service = ExpirationService(user_repo, proxy_repo)
    notif_service = NotificationService(bot, exp_service)
    worker = BackgroundScheduler(notif_service)
    
    # Запускаем фоновый воркер
    asyncio.create_task(scheduler.run_interval())
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        bot_logger.error(f"Критическая ошибка: {e}")
    finally:
        await bot.session.close()
        bot_logger.info("Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main())
