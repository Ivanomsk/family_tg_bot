from aiogram import Router, F, types
from aiogram.filters import Command

from services.auth_service import is_admin
from services.vpn_service import test_ssh_connection

router = Router()


@router.message(Command("vpn_test"))
async def cmd_vpn_test(message: types.Message):
    """Проверить подключение к VPN серверу"""

    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён")
        return

    await message.answer("🔌 Проверяю SSH подключение...")

    result = test_ssh_connection()

    if 'error' in result:
        await message.answer(f"❌ Ошибка: {result['error']}")
        return

    response = "✅ <b>SSH подключено!</b>\n\n"
    response += f"<b>Docker:</b>\n<code>{result['docker'][:500]}</code>\n\n"
    response += f"<b>WireGuard:</b>\n<code>{result['wireguard'][:800]}</code>"

    await message.answer(response, parse_mode="HTML")


@router.callback_query(F.data == "vpn_test_conn")
async def vpn_test_conn(callback: types.CallbackQuery):
    """Проверить подключение через кнопку"""

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return

    await callback.answer("🔌 Проверяю...")

    result = test_ssh_connection()

    if 'error' in result:
        await callback.message.answer(f"❌ Ошибка: {result['error']}")
        return

    response = "✅ <b>SSH подключено!</b>\n\n"
    response += f"<b>Docker:</b>\n<code>{result['docker'][:300]}</code>\n\n"
    response += f"<b>WireGuard:</b>\n<code>{result['wireguard'][:500]}</code>"

    await callback.message.answer(response, parse_mode="HTML")
