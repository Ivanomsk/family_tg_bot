from aiogram import Router, F, types
from aiogram.filters import Command
from config import ADMIN_IDS
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

@router.callback_query(F.data == "admin_vpn_revoke")
async def admin_vpn_revoke_menu(callback: types.CallbackQuery):
    """Меню отзыва VPN"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    text = (
        "🗑️ <b>ОТОЗВАТЬ VPN</b>\n\n"
        "Используйте команду:\n"
        "<code>/revoke username</code> — отозвать ВСЕ конфиги пользователя\n"
        "<code>/revoke username public_key</code> — отозвать конкретный\n\n"
        "📝 <b>Примеры:</b>\n"
        "<code>/revoke Ivan_Mos</code>\n"
        "<code>/revoke Ivan_Mos pXsM/uIIRo0xv0AMTnVF</code>\n\n"
        "💡 <i>Конфиг будет удалён с сервера и помечен как неактивный</i>"
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_keyboard("admin_users").as_markup()
    )
