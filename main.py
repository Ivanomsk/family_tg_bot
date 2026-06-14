import asyncio
import os
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, ADMIN_IDS
from handlers import start, vpn, proxy, admin, backup, errors
from utils.expiry import check_all_vpn_expiry, check_all_proxy_expiry
from utils.logger import standard_logger, audit_logger

# ✅ Используем логгеры из utils.logger (НЕ создаём новые!)
logger = standard_logger


# ============================================
# АВТОПРОВЕРКА ИСТЁКШИХ VPN И ПРОКСИ
# ============================================

async def check_all_expiry_on_startup(bot):
    """Проверяет истёкшие VPN и прокси при запуске и уведомляет админа"""
    # Небольшая задержка, чтобы бот успел запуститься
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
        
        logger.info(
            f"🔔 Отправлен отчёт: VPN {len(vpn_expired)} истекли/{len(vpn_expiring)} истекают, "
            f"Прокси {len(proxy_expired)} истекли/{len(proxy_expiring)} истекают"
        )
        
        # ✅ AUDIT-ЛОГ АВТОПРОВЕРКИ
        audit_logger.info(
            f"ACTION:STARTUP_EXPIRY_CHECK | "
            f"VPN_EXPIRED:{len(vpn_expired)} | "
            f"VPN_EXPIRING:{len(vpn_expiring)} | "
            f"PROXY_EXPIRED:{len(proxy_expired)} | "
            f"PROXY_EXPIRING:{len(proxy_expiring)}"
        )
    else:
        logger.info("✅ Все VPN и прокси активны")


# ============================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(vpn.router)
    dp.include_router(proxy.router)
    dp.include_router(admin.router)
    dp.include_router(backup.router)
    dp.include_router(errors.router)
    
    logger.info("🧠 Санитар Дурдома запущен!")
    audit_logger.info("=== БОТ ЗАПУЩЕН ===")
    
    # Запускаем проверку истёкших VPN и прокси при старте
    asyncio.create_task(check_all_expiry_on_startup(bot))
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())