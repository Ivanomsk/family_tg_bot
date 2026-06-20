import asyncio
import os
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, ADMIN_IDS
from handlers import start, vpn, proxy, admin, backup, errors, vpn_admin
from handlers import extend
from utils.expiry import check_all_vpn_expiry, check_all_proxy_expiry
from utils.logger import standard_logger, audit_logger
from utils.notifications import (
    check_and_send_personal_notifications,
    check_proxy_notifications
)
from utils.vpn_manager import delete_expired_vpn

logger = standard_logger


async def check_all_expiry_on_startup(bot):
    await asyncio.sleep(5)
    try:
        vpn_expired, vpn_expiring = check_all_vpn_expiry()
        proxy_expired, proxy_expiring = check_all_proxy_expiry()
    except Exception as e:
        logger.error(f"Ошибка при проверке срока действия: {e}")
        return

    if vpn_expired or vpn_expiring or proxy_expired or proxy_expiring:
        text = "🔔 <b>Автоматическая проверка срока</b>\n\n"
        if vpn_expired:
            text += f"❌ <b>VPN ИСТЕКЛИ ({len(vpn_expired)}):</b>\n"
            for item in vpn_expired[:5]:
                text += f"  • @{item['username']} — {item['filename']}\n"
            if len(vpn_expired) > 5:
                text += f"  • ... и ещё {len(vpn_expired) - 5}\n"
            text += "\n"
        if vpn_expiring:
            text += f"⚠️ <b>VPN ИСТЕКАЮТ ({len(vpn_expiring)}):</b>\n"
            for item in vpn_expiring[:5]:
                text += f"  • @{item['username']} — {item['filename']} ({item['days_left']} дн.)\n"
            text += "\n"
        if proxy_expired:
            text += f"❌ <b>ПРОКСИ ИСТЕКЛИ ({len(proxy_expired)}):</b>\n"
            for item in proxy_expired[:5]:
                text += f"  • ID {item['user_id']} — {item['proxy_name']}\n"
            if len(proxy_expired) > 5:
                text += f"  • ... и ещё {len(proxy_expired) - 5}\n"
            text += "\n"
        if proxy_expiring:
            text += f"⚠️ <b>ПРОКСИ ИСТЕКАЮТ ({len(proxy_expiring)}):</b>\n"
            for item in proxy_expiring[:5]:
                text += f"  • ID {item['user_id']} — {item['proxy_name']} ({item['days_left']} дн.)\n"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Не удалось отправить отчёт админу {admin_id}: {e}")
        logger.info(f"🔔 Отправлен отчёт: VPN {len(vpn_expired)} истекли/{len(vpn_expiring)} истекают, Прокси {len(proxy_expired)} истекли/{len(proxy_expiring)} истекают")
        audit_logger.info(f"ACTION:STARTUP_EXPIRY_CHECK | VPN_EXPIRED:{len(vpn_expired)} | VPN_EXPIRING:{len(vpn_expiring)} | PROXY_EXPIRED:{len(proxy_expired)} | PROXY_EXPIRING:{len(proxy_expiring)}")
    else:
        logger.info("✅ Все VPN и прокси активны")


async def scheduled_tasks(bot):
    await asyncio.sleep(10)
    logger.info("🔄 Фоновая задача scheduled_tasks запущена!")
    while True:
        try:
            # VPN
            logger.info("🔍 Проверка VPN...")
            deleted = delete_expired_vpn()
            if deleted > 0:
                logger.info(f"🗑️ Удалено {deleted} истекших VPN")
            sent_vpn = await check_and_send_personal_notifications(bot)
            if sent_vpn > 0:
                logger.info(f"🔔 Отправлено {sent_vpn} личных уведомлений VPN")
            
            # Прокси
            logger.info("🔍 Проверка прокси...")
            sent_proxy = await check_proxy_notifications(bot)
            if sent_proxy > 0:
                logger.info(f"🔔 Отправлено {sent_proxy} уведомлений о прокси")
            
            # Общая проверка сроков
            vpn_expired, vpn_expiring = check_all_vpn_expiry()
            proxy_expired, proxy_expiring = check_all_proxy_expiry()
            
            if vpn_expired or vpn_expiring or proxy_expired or proxy_expiring:
                logger.info(f"📊 Статус: VPN истекло {len(vpn_expired)}, истекает {len(vpn_expiring)} | Прокси истекло {len(proxy_expired)}, истекает {len(proxy_expiring)}")
            
            await asyncio.sleep(21600)
        except Exception as e:
            logger.error(f"❌ Ошибка в scheduled_tasks: {e}")
            await asyncio.sleep(3600)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    dp.include_router(start.router)
    dp.include_router(vpn_admin.router)
    dp.include_router(vpn.router)
    dp.include_router(proxy.router)
    dp.include_router(admin.router)
    dp.include_router(backup.router)
    dp.include_router(errors.router)
    dp.include_router(extend.router)
    
    logger.info("🧠 Санитар Дурдома запущен!")
    audit_logger.info("=== БОТ ЗАПУЩЕН ===")
    
    asyncio.create_task(check_all_expiry_on_startup(bot))
    asyncio.create_task(scheduled_tasks(bot))
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
