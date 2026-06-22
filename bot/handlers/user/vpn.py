from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatType
from bot.services.vpn.core import VPNCoreService
from bot.services.vpn.issue import VPNIssueService
from bot.repositories.user_repository import UserRepository
from bot.config import DATA_DIR

router = Router()

user_repo = UserRepository(DATA_DIR)
core = VPNCoreService(user_repo)
issue_service = VPNIssueService(core)

@router.message(Command("vpn"))
async def cmd_vpn(message: Message):
    user = message.from_user
    vpn_user = await core.get_user(user.id)

    if message.chat.type == ChatType.PRIVATE:
        if vpn_user and vpn_user.is_active and not vpn_user.is_expired():
            days_left = vpn_user.days_left()
            await message.answer(
                f"✅ <b>Ваш VPN активен</b>\n"
                f"📅 Осталось дней: <b>{days_left}</b>\n"
                f"🆔 ID: {user.id}"
            )
        elif vpn_user and vpn_user.is_active and vpn_user.is_expired():
            await message.answer(
                f"❌ <b>Ваш VPN истёк</b>\n"
                f"Свяжитесь с администратором для продления."
            )
        else:
            await message.answer(
                f"❌ <b>У вас нет активного VPN</b>\n"
                f"Обратитесь к администратору для выдачи ключа."
            )
        return

    safe_name = user.full_name or user.username or f"Пользователь {user.id}"
    await message.answer(
        f"ℹ️ <b>{safe_name}, это команда для управления VPN.</b>\n\n"
        f"• Узнать статус и управлять ключом можно <b>только в личных сообщениях</b>.\n"
        f"• Нажми на мою иконку и выбери «Запустить», чтобы открыть ЛС.\n"
        f"• В ЛС доступны: /vpn, /start, /proxy."
    )
