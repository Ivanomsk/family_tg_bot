from aiogram import Router, F, types
from aiogram.filters import Command

from services.auth_service import is_admin
from services.vpn_service import list_vpn_users

router = Router()


@router.message(Command("vpn_list"))
async def cmd_vpn_list(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён")
        return

    await message.answer("📋 Загружаю список...")

    result = list_vpn_users()

    if 'error' in result:
        await message.answer(f"❌ Ошибка: {result['error']}")
        return

    clients = result['users']

    if not clients:
        await message.answer("📭 Нет пользователей")
        return

    text = f"📋 <b>VPN пользователи ({len(clients)}):</b>\n\n"

    for i, client in enumerate(clients, 1):
        name = client.get('userData', {}).get('clientName', 'Unknown')
        ip = client.get('userData', {}).get('allowedIps', 'Unknown')
        created = client.get('userData', {}).get('creationDate', '')
        received = client.get('userData', {}).get('dataReceived', '0 B')
        sent = client.get('userData', {}).get('dataSent', '0 B')
        handshake = client.get('userData', {}).get('latestHandshake', 'Never')
        pubkey = client.get('clientId', '')

        text += f"{i}. <b>{name}</b>\n"
        text += f"📍 <code>{ip}</code>\n"
        text += f"📅 {created}\n"
        text += f"📥 {received} | 📤 {sent}\n"
        text += f"🔄 {handshake}\n"
        text += f"🔑 <code>{pubkey[:30]}...</code>\n\n"

    for i in range(0, len(text), 4000):
        await message.answer(text[i:i+4000], parse_mode="HTML")


@router.callback_query(F.data == "vpn_show_list")
async def vpn_show_list(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return

    await callback.answer()
    fake_message = callback.message
    fake_message.from_user = callback.from_user

    await cmd_vpn_list(fake_message)
