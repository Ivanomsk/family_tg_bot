from aiogram import Router, F, types
from aiogram.filters import Command
from config import ADMIN_IDS
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

@router.callback_query(F.data == "admin_vpn_list")
async def admin_vpn_list(callback: types.CallbackQuery):
    """Список VPN пользователей"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    vpn_users = load_vpn_db()
    if not vpn_users:
        await callback.message.edit_text(
            "📭 Нет активных VPN конфигов.",
            reply_markup=get_back_keyboard("admin_users").as_markup(),
            parse_mode="HTML"
        )
        return
    
    users = {}
    for public_key, data in vpn_users.items():
        username = data.get('username', 'unknown')
        user_id_data = data.get('user_id')
        active = data.get('active', True)
        permanent = data.get('permanent', False)
        expires_at = data.get('expires_at', 'не указана')
        
        if expires_at != 'не указана':
            try:
                dt = datetime.fromisoformat(expires_at)
                expires_display = dt.strftime('%d.%m.%Y %H:%M')
            except:
                expires_display = expires_at
        else:
            expires_display = 'не указана'
        
        if username not in users:
            users[username] = {
                'user_id': user_id_data,
                'configs': [],
                'total': 0
            }
        users[username]['configs'].append({
            'active': active,
            'permanent': permanent,
            'expires_at': expires_display
        })
        users[username]['total'] += 1
    
    text = "📋 <b>СПИСОК VPN ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"
    
    for username, data in sorted(users.items()):
        user_id_data = data['user_id']
        username_display = f"@{username}" if username != 'unknown' else f"ID:{user_id_data}"
        text += f"👤 {username_display} (ID: {user_id_data})\n"
        text += f"   📁 Конфигов: {data['total']}\n"
        for conf in data['configs']:
            if conf['permanent']:
                status = "♾️ Бессрочный"
            elif conf['active']:
                status = "✅ Активен"
            else:
                status = "❌ Неактивен"
            text += f"      {status} | истекает: {conf['expires_at']}\n"
        text += "\n"
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_users").as_markup()
    )
