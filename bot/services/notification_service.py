from bot.utils.logger import bot_logger

class NotificationService:
    def __init__(self, bot, expiration_service):
        self.bot = bot
        self.exp_service = expiration_service

    async def notify_expiring_vpn(self):
        """Отправить уведомления об истекающих VPN"""
        expiring = await self.exp_service.get_expiring_vpn_users()
        if not expiring:
            bot_logger.info("Нет истекающих VPN-ключей.")
            return
        
        for user in expiring:
            days_left = user.days_left()
            try:
                await self.bot.send_message(
                    user.tg_id,
                    f"⚠️ <b>Уведомление о сроке VPN</b>\n\n"
                    f"Ваш VPN-ключ истекает через <b>{days_left}</b> дн.\n"
                    f"Пожалуйста, свяжитесь с администратором для продления."
                )
                bot_logger.info(f"Уведомление отправлено пользователю {user.tg_id} (VPN, {days_left} дн.)")
            except Exception as e:
                bot_logger.error(f"Ошибка отправки уведомления VPN для {user.tg_id}: {e}")

    async def notify_expiring_proxy(self):
        """Отправить уведомления об истекающих Прокси"""
        expiring = await self.exp_service.get_expiring_proxy_users()
        if not expiring:
            bot_logger.info("Нет истекающих Прокси-ключей.")
            return
        
        for user in expiring:
            days_left = user.days_left()
            try:
                await self.bot.send_message(
                    user.tg_id,
                    f"⚠️ <b>Уведомление о сроке Прокси</b>\n\n"
                    f"Ваш Прокси-доступ истекает через <b>{days_left}</b> дн.\n"
                    f"Пожалуйста, свяжитесь с администратором для продления."
                )
                bot_logger.info(f"Уведомление отправлено пользователю {user.tg_id} (Прокси, {days_left} дн.)")
            except Exception as e:
                bot_logger.error(f"Ошибка отправки уведомления Прокси для {user.tg_id}: {e}")

    async def notify_revoke(self, tg_id: int, service_type: str = "VPN"):
        """Отправить уведомление об отзыве ключа"""
        try:
            await self.bot.send_message(
                tg_id,
                f"🚫 <b>Ваш {service_type}-ключ был отозван администратором.</b>\n\n"
                f"Запросите новый ключ или свяжитесь с администратором.\n"
                f"Для обратной связи используйте команду /feedback (будет реализована позже)."
            )
            bot_logger.info(f"Уведомление об отзыве отправлено пользователю {tg_id} ({service_type})")
        except Exception as e:
            bot_logger.error(f"Ошибка отправки уведомления об отзыве для {tg_id}: {e}")
