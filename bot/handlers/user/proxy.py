from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatType
from bot.services.proxy.core import ProxyCoreService
from bot.services.proxy.issue import ProxyIssueService
from bot.repositories.proxy_repository import ProxyRepository
from bot.config import DATA_DIR

router = Router()

proxy_repo = ProxyRepository(DATA_DIR)
core = ProxyCoreService(proxy_repo)
issue_service = ProxyIssueService(core)

@router.message(Command("proxy"))
async def cmd_proxy(message: Message):
    user = message.from_user
    proxy_user = await core.get_user(user.id)

    if message.chat.type == ChatType.PRIVATE:
        if proxy_user and proxy_user.is_active and not proxy_user.is_expired():
            days_left = proxy_user.days_left()
            await message.answer(
                f"✅ <b>Ваш Прокси активен</b>\n"
                f"📅 Осталось дней: <b>{days_left}</b>\n"
                f"🆔 ID: {user.id}"
            )
        elif proxy_user and proxy_user.is_active and proxy_user.is_expired():
            await message.answer(
                f"❌ <b>Ваш Прокси истёк</b>\n"
                f"Свяжитесь с администратором для продления."
            )
        else:
            await message.answer(
                f"❌ <b>У вас нет активного Прокси</b>\n"
                f"Обратитесь к администратору для выдачи ключа."
            )
        return

    safe_name = user.full_name or user.username or f"Пользователь {user.id}"
    await message.answer(
        f"ℹ️ <b>{safe_name}, это команда для управления Прокси.</b>\n\n"
        f"• Узнать статус и управлять прокси можно <b>только в личных сообщениях</b>.\n"
        f"• Нажми на мою иконку и выбери «Запустить», чтобы открыть ЛС.\n"
        f"• В ЛС доступны: /proxy, /start, /vpn."
    )
