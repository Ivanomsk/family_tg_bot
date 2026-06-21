import os
import tempfile

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states.forms import VpnIssue
from services.auth_service import is_admin
from services.vpn_service import issue_vpn_config
from utils.logger import logger, audit_logger

router = Router()


@router.message(Command("vpn_issue"))
async def cmd_vpn_issue(message: types.Message):
    """Выдать VPN конфиг пользователю"""

    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён")
        return

    args = message.text.split()

    if len(args) < 2:
        await message.answer(
            "📝 Использование:\n"
            "<code>/vpn_issue @username</code>\n\n"
            "Пример:\n"
            "<code>/vpn_issue ivanov</code>",
            parse_mode="HTML"
        )
        return

    username = args[1].lstrip('@')

    await message.answer(
        f"⏳ Генерирую VPN конфиг для @{username}..."
    )

    result = issue_vpn_config(username, user_id=None)

    if 'error' in result:
        await message.answer(f"❌ Ошибка: {result['error']}")
        return

    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.conf',
        delete=False
    ) as f:
        f.write(result['config_string'])
        temp_path = f.name

    try:
        await message.answer_document(
            document=FSInputFile(
                temp_path,
                filename=f"vpn_{username}.conf"
            ),
            caption=(
                f"✅ <b>VPN конфиг выдан</b>\n\n"
                f"👤 Пользователь: @{username}\n"
                f"📍 IP: <code>{result['ip']}</code>\n"
                f"⏰ Срок: до {result['expires_at']}\n\n"
                f"🔑 Public key:\n"
                f"<code>{result['public_key']}</code>"
            ),
            parse_mode="HTML"
        )

    finally:
        os.remove(temp_path)


@router.callback_query(F.data == "vpn_issue_start")
async def vpn_issue_start(
        callback: types.CallbackQuery,
        state: FSMContext
):
    """Начало выдачи конфига"""

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(
        text="❌ Отмена",
        callback_data="vpn_admin_menu"
    )
    builder.adjust(1)

    await callback.message.edit_text(
        "➕ <b>Выдача VPN конфига</b>\n\n"
        "Отправьте имя пользователя (без @)\n\n"
        "Пример:\n"
        "<code>ivanov</code>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )

    await state.set_state(VpnIssue.waiting_for_username)

    await callback.answer()


@router.message(VpnIssue.waiting_for_username)
async def process_vpn_issue_username(
        message: types.Message,
        state: FSMContext
):
    """Обработка username"""

    audit_logger.info(
        f"🔐 VPN_ISSUE_START | USER:{message.from_user.id}"
    )

    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён")
        await state.clear()
        return

    username = message.text.strip().lstrip('@')

    await message.answer(
        f"⏳ Генерирую VPN конфиг для @{username}..."
    )

    result = issue_vpn_config(
        username,
        user_id=message.from_user.id
    )

    if 'error' in result:
        await message.answer(
            f"❌ Ошибка: {result['error']}"
        )
        await state.clear()
        return

    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.conf',
        delete=False
    ) as f:
        f.write(result['config_string'])
        temp_path = f.name

    try:

        await message.answer_document(
            document=FSInputFile(
                temp_path,
                filename=f"vpn_{username}.conf"
            ),
            caption=(
                f"✅ <b>VPN конфиг выдан</b>\n\n"
                f"👤 Пользователь: @{username}\n"
                f"📍 IP: <code>{result['ip']}</code>\n"
                f"⏰ Срок: до {result['expires_at']}\n\n"
                f"🔑 Public key:\n"
                f"<code>{result['public_key']}</code>"
            ),
            parse_mode="HTML"
        )

    finally:
        os.remove(temp_path)
        await state.clear()


@router.callback_query(
    F.data == "vpn_admin_menu",
    VpnIssue.waiting_for_username
)
async def cancel_vpn_issue(
        callback: types.CallbackQuery,
        state: FSMContext
):
    """Отмена выдачи VPN"""

    await state.clear()

    from .menu import vpn_admin_menu

    await vpn_admin_menu(callback)

