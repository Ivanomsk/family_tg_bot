from aiogram import Router, types
from aiogram.filters import Command

from services.auth_service import is_admin
from services.vpn_service import revoke_vpn_config

router = Router()


@router.message(Command("vpn_revoke"))
async def cmd_vpn_revoke(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён")
        return

    args = message.text.split()

    if len(args) < 2:
        await message.answer(
            "📝 Использование:\n<code>/vpn_revoke PUBLIC_KEY</code>",
            parse_mode="HTML"
        )
        return

    public_key = args[1]

    await message.answer("⏳ Отзываю конфиг...")

    result = revoke_vpn_config(public_key)

    if 'error' in result:
        await message.answer(f"❌ Ошибка: {result['error']}")
        return

    await message.answer(
        f"✅ Конфиг отозван\n\n"
        f"🔑 <code>{public_key[:40]}...</code>",
        parse_mode="HTML"
    )
