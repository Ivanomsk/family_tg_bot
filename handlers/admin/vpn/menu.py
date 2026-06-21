from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.auth_service import is_admin

router = Router()


@router.callback_query(F.data == "vpn_admin_menu")
async def vpn_admin_menu(callback: types.CallbackQuery):
    """Меню управления VPN"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️ Доступ запрещён", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Список пользователей", callback_data="vpn_show_list")
    builder.button(text="➕ Выдать конфиг", callback_data="vpn_issue_start")
    builder.button(text="🔌 Проверить подключение", callback_data="vpn_test_conn")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(1)

    await callback.message.edit_text(
        "🔐 <b>Управление VPN</b>\n\nВыберите действие:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()
