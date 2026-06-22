import asyncio
from bot.services.notification_service import NotificationService
from bot.utils.logger import cron_logger

class BackgroundScheduler:
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service

    async def run_interval(self, interval_seconds: int = 21600):
        while True:
            cron_logger.info("Запуск фоновой проверки истекающих ключей...")
            try:
                await self.notification_service.notify_expiring_vpn()
                await self.notification_service.notify_expiring_proxy()
                cron_logger.info("Фоновая проверка завершена.")
            except Exception as e:
                cron_logger.error(f"Критическая ошибка в фоновом воркере: {e}", exc_info=True)
            await asyncio.sleep(interval_seconds)
