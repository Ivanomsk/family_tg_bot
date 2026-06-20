"""Админские хендлеры для управления VPN"""

import os
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import tempfile
from aiogram.fsm.context import FSMContext
from states.forms import VpnIssue
from utils.vpn_manager import (
    issue_vpn_config, 
    revoke_vpn_config, 
    list_vpn_users,
    test_ssh_connection
)

from utils.logger import standard_logger, audit_logger
logger = standard_logger

# Загружаем ADMIN_IDS
from config import ADMIN_IDS

router = Router()


def is_admin(user_id: int) -> bool:
    """Проверка что пользователь - админ"""
    return user_id in ADMIN_IDS


# ==========================================
# КОМАНДЫ УПРАВЛЕНИЯ VPN
# ==========================================

@router.message(Command("vpn_issue"))
async def cmd_vpn_issue(message: types.Message):
    """Выдать VPN конфиг пользователю"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "📝 Использование: <code>/vpn_issue @username</code>\n\n"
            "Пример: <code>/vpn_issue ivanov</code>",
            parse_mode="HTML"
        )
        return
    
    username = args[1].lstrip('@')
    await message.answer(f"⏳ Генерирую VPN конфиг для @{username}...")
    
    result = issue_vpn_config(username, user_id=None)
    
    if 'error' in result:
        await message.answer(f"❌ Ошибка: {result['error']}")
        return
    
    # Сохраняем конфиг во временный файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
        f.write(result['config_string'])
        temp_path = f.name
    
    try:
        # Отправляем файл
        await message.answer_document(
            document=FSInputFile(temp_path, filename=f"vpn_{username}.conf"),
            caption=(
                f"✅ <b>VPN конфиг выдан</b>\n\n"
                f"👤 Пользователь: @{username}\n"
                f"📍 IP: <code>{result['ip']}</code>\n"
                f"⏰ Срок: до {result['expires_at']}\n\n"
                f"🔑 Public key:\n<code>{result['public_key']}</code>"
            ),
            parse_mode="HTML"
        )
        
        # Уведомление в админ-чат (если настроен)
        admin_chat_id = os.getenv('ALLOWED_CHAT_ID')
        if admin_chat_id:
            try:
                from main import bot
                await bot.send_message(
                    admin_chat_id,
                    f"🔐 <b>Выдан VPN конфиг</b>\n\n"
                    f"👤 Пользователь: @{username}\n"
                    f"📍 IP: {result['ip']}\n"
                    f"⏰ Истекает: {result['expires_at']}",
                    parse_mode="HTML"
                )
            except Exception:
                pass
    finally:
        os.remove(temp_path)


@router.message(Command("vpn_revoke"))
async def cmd_vpn_revoke(message: types.Message):
    """Отозвать VPN конфиг"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔️ Доступ запрещён")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "📝 Использование: <code>/vpn_revoke PUBLIC_KEY</code>\n\n"
            "Скопируйте ключ из /vpn_list",
            parse_mode="HTML"
        )
        return
    
    public_key = args[1]
    await message.answer("⏳ отзываю конфиг...")
    
    result = revoke_vpn_config(public_key)
    
    if 'error' in result:
        await message.answer(f"❌ Ошибка: {result['error']}")
        return
    
    await message.answer(
        f"✅ <b>Конфиг отозван</b>\n\n"
        f"🔑 Key: <code>{public_key[:40]}...</code>\n"
        f"📍 IP освобождён",
        parse_mode="HTML"
    )


@router.message(Command("vpn_list"))
async def cmd_vpn_list(message: types.Message):
    """Список VPN пользователей"""
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
        text += f"   📍 IP: <code>{ip}</code>\n"
        text += f"   📅 Создан: {created}\n"
        text += f"   📥 Получено: {received} | 📤 Отправлено: {sent}\n"
        text += f"   🔄 Handshake: {handshake}\n"
        text += f"   🔑 <code>{pubkey[:30]}...</code>\n\n"
    
    # Отправляем частями (Telegram лимит 4096 символов)
    chunk_size = 4000
    for i in range(0, len(text), chunk_size):
        await message.answer(text[i:i+chunk_size], parse_mode="HTML")


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


# ==========================================
# КНОПКИ В МЕНЮ АДМИНА
# ==========================================

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
        "🔐 <b>Управление VPN</b>\n\n"
        "Выберите действие:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "vpn_show_list")
async def vpn_show_list(callback: types.CallbackQuery):
    """Показать список через кнопку"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return
    
    await callback.answer("📋 Загружаю...")
    
    result = list_vpn_users()
    
    if 'error' in result:
        await callback.message.answer(f"❌ Ошибка: {result['error']}")
        return
    
    clients = result['users']
    
    if not clients:
        await callback.message.answer("📭 Нет пользователей")
        return
    
    text = f"📋 <b>VPN пользователи ({len(clients)}):</b>\n\n"
    
    for i, client in enumerate(clients, 1):
        name = client.get('userData', {}).get('clientName', 'Unknown')
        ip = client.get('userData', {}).get('allowedIps', 'Unknown')
        created = client.get('userData', {}).get('creationDate', '')
        received = client.get('userData', {}).get('dataReceived', '0 B')
        sent = client.get('userData', {}).get('dataSent', '0 B')
        
        text += f"{i}. <b>{name}</b>\n"
        text += f"   📍 {ip} | 📅 {created}\n"
        text += f"   📥 {received} | 📤 {sent}\n\n"
    
    # Отправляем частями
    chunk_size = 4000
    for i in range(0, len(text), chunk_size):
        await callback.message.answer(text[i:i+chunk_size], parse_mode="HTML")


@router.callback_query(F.data == "vpn_issue_start")
async def vpn_issue_start(callback: types.CallbackQuery, state: FSMContext):
    """Начало выдачи конфига - запрашиваем username"""
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔️", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="vpn_admin_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        "➕ <b>Выдача VPN конфига</b>\n\n"
        "Отправьте имя пользователя (без @):\n\n"
        "Пример: <code>ivanov</code>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    
    # Устанавливаем состояние ожидания username
    await state.set_state(VpnIssue.waiting_for_username)
    await callback.answer()


@router.message(VpnIssue.waiting_for_username)
async def process_vpn_issue_username(message: types.Message, state: FSMContext):
    """Обработка введённого username"""
    audit_logger.info(f"🔐 VPN_ISSUE_START | USER:{message.from_user.id} | USERNAME:{message.from_user.username}")
    logger.info(f"🔐 Запрос VPN конфига от @{message.from_user.username} (ID: {message.from_user.id})")
    
    if not is_admin(message.from_user.id):
        audit_logger.warning(f"⛔️ VPN_ISSUE_DENIED | USER:{message.from_user.id}")
        logger.warning(f"⛔️ Попытка доступа не-админа: {message.from_user.id}")
        await message.answer("⛔️ Доступ запрещён")
        await state.clear()
        return
    
    username = message.text.strip().lstrip('@')
    audit_logger.info(f"📝 VPN_ISSUE_REQUEST | USER:{message.from_user.id} | TARGET:@{username}")
    logger.info(f"📝 Выдача конфига для: @{username}")
    
    await message.answer(f"⏳ Генерирую VPN конфиг для @{username}...")
    
    result = issue_vpn_config(username, user_id=message.from_user.id)
    
    if 'error' in result:
        audit_logger.error(f"❌ VPN_ISSUE_ERROR | USER:{message.from_user.id} | TARGET:@{username} | ERROR:{result['error']}")
        logger.error(f"❌ Ошибка выдачи конфига для @{username}: {result['error']}")
        await message.answer(f"❌ Ошибка: {result['error']}")
        await state.clear()
        return
    
    audit_logger.info(f"✅ VPN_ISSUE_SUCCESS | USER:{message.from_user.id} | TARGET:@{username} | IP:{result['ip']}")
    logger.info(f"✅ Конфиг выдан для @{username} (IP: {result['ip']})")
    
    # Сохраняем конфиг во временный файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
        f.write(result['config_string'])
        temp_path = f.name
    
    try:
        # Отправляем файл
        await message.answer_document(
            document=FSInputFile(temp_path, filename=f"vpn_{username}.conf"),
            caption=(
                f"✅ <b>VPN конфиг выдан</b>\n\n"
                f"👤 Пользователь: @{username}\n"
                f"📍 IP: <code>{result['ip']}</code>\n"
                f"⏰ Срок: до {result['expires_at']}\n\n"
                f"🔑 Public key:\n<code>{result['public_key']}</code>"
            ),
            parse_mode="HTML"
        )
        audit_logger.info(f"📤 VPN_ISSUE_SENT | USER:{message.from_user.id} | TARGET:@{username}")
        logger.info(f"📤 Файл отправлен для @{username}")
    finally:
        os.remove(temp_path)
        await state.clear()


@router.callback_query(F.data == "vpn_admin_menu", VpnIssue.waiting_for_username)
async def cancel_vpn_issue(callback: types.CallbackQuery, state: FSMContext):
    """Отмена выдачи VPN конфига"""
    await state.clear()
    await vpn_admin_menu(callback)


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
