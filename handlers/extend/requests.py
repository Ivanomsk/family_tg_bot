from aiogram import Router, types

from repositories.vpn_repository import load_vpn_db
from services.vpn_extend_service import extend_vpn_config
from config import ADMIN_IDS

router = Router()

# ============================================
# ПРОДЛЕНИЕ ПО КНОПКЕ (АДМИН ОДОБРЯЕТ)
# ============================================

@router.callback_query(lambda c: c.data and c.data.startswith('req_ext_'))
async def request_extend(callback: types.CallbackQuery):
    """Пользователь запрашивает продление конфига"""
    parts = callback.data.split('_', 2)
    if len(parts) < 3:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        user_id = int(parts[1])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    short_hash = parts[2]
    
    if callback.from_user.id != user_id:
        await callback.answer("⛔ Это не ваш конфиг!", show_alert=True)
        return
    
    # Ищем конфиг по короткому хешу
    vpn_users = load_vpn_db()
    config_hash = None
    config_data = None
    for ch, cd in vpn_users.items():
        if ch.startswith(short_hash) or ch[:20] == short_hash:
            config_hash = ch
            config_data = cd
            break
    
    if not config_data:
        await callback.answer("❌ Конфиг не найден", show_alert=True)
        return
    
    username = config_data.get('username', 'unknown')
    expires_at = config_data.get('expires_at', 'не указана')
    user_mention = f"@{callback.from_user.username}" if callback.from_user.username else f"ID:{user_id}"
    
    admin_text = (
        f"🔄 <b>Запрос на продление</b>\n\n"
        f"👤 <b>Пользователь:</b> {user_mention}\n"
        f"📁 <b>Конфиг:</b> {username}\n"
        f"📅 <b>Истекает:</b> {expires_at}\n\n"
        f"Действия:"
    )
    
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=f"app_ext_{user_id}_{config_hash[:20]}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"rej_ext_{user_id}_{config_hash[:20]}"
            )
        ]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                admin_text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Не удалось отправить запрос админу {admin_id}: {e}")
    
    await callback.answer("✅ Запрос на продление отправлен администратору!")
    await callback.message.edit_text(
        "🔄 <b>Запрос на продление отправлен!</b>\n\n"
        "Администратор рассмотрит ваш запрос в ближайшее время.\n"
        "Вы получите уведомление о решении.",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_vpn").as_markup()
    )
    
    audit_logger.info(
        f"ACTION:REQUEST_EXTEND | USER:{user_id} | "
        f"CONFIG:{config_hash[:20]}... | EXPIRES:{expires_at}"
    )

@router.callback_query(lambda c: c.data and c.data.startswith('app_ext_'))
async def approve_extend(callback: types.CallbackQuery):
    """Админ одобряет продление"""
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split('_', 2)
    if len(parts) < 3:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        target_user_id = int(parts[1])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    short_hash = parts[2]
    
    # Ищем конфиг по короткому хешу
    vpn_users = load_vpn_db()
    config_hash = None
    for ch in vpn_users.keys():
        if ch.startswith(short_hash) or ch[:20] == short_hash:
            config_hash = ch
            break
    
    if not config_hash:
        await callback.answer("❌ Конфиг не найден", show_alert=True)
        return
    
    success, result = extend_vpn_config(target_user_id, config_hash, days=30)
    
    if success:
        try:
            await callback.bot.send_message(
                target_user_id,
                f"✅ <b>Ваш запрос на продление одобрен!</b>\n\n"
                f"📅 Новая дата истечения: <code>{result.isoformat()}</code>\n\n"
                f"Вы можете посмотреть все конфиги по команде /my_configs",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось уведомить пользователя {target_user_id}: {e}")
        
        await callback.answer("✅ Конфиг продлен на 30 дней!")
        await callback.message.edit_text(
            f"✅ <b>Продление одобрено!</b>\n\n"
            f"👤 Пользователь получил уведомление.\n"
            f"📅 Новая дата истечения: <code>{result.isoformat()}</code>\n\n"
            f"🔑 Хеш: <code>{config_hash[:24]}...</code>",
            parse_mode="HTML"
        )
        
        audit_logger.info(
            f"ACTION:APPROVE_EXTEND | ADMIN:{user_id} | "
            f"USER:{target_user_id} | CONFIG:{config_hash[:20]}..."
        )
    else:
        await callback.answer(f"❌ Ошибка: {result}", show_alert=True)
        try:
            await callback.bot.send_message(
                target_user_id,
                f"❌ <b>Ошибка при продлении</b>\n\n"
                f"Не удалось продлить конфиг. Обратитесь к администратору.",
                parse_mode="HTML"
            )
        except:
            pass

@router.callback_query(lambda c: c.data and c.data.startswith('rej_ext_'))
async def reject_extend(callback: types.CallbackQuery):
    """Админ отклоняет продление"""
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split('_', 2)
    if len(parts) < 3:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        target_user_id = int(parts[1])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    short_hash = parts[2]
    
    # Ищем конфиг по короткому хешу
    vpn_users = load_vpn_db()
    config_hash = None
    for ch in vpn_users.keys():
        if ch.startswith(short_hash) or ch[:20] == short_hash:
            config_hash = ch
            break
    
    try:
        await callback.bot.send_message(
            target_user_id,
            f"❌ <b>Ваш запрос на продление отклонён</b>\n\n"
            f"Администратор отклонил ваш запрос.\n"
            f"Если у вас есть вопросы — обратитесь к администратору.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {target_user_id}: {e}")
    
    await callback.answer("❌ Запрос отклонен")
    await callback.message.edit_text(
        f"❌ <b>Запрос отклонен</b>\n\n"
        f"👤 Пользователь получил уведомление об отказе.\n"
        f"🔑 Хеш: <code>{config_hash[:24] if config_hash else '...'}</code>",
        parse_mode="HTML"
    )
    
    audit_logger.info(
        f"ACTION:REJECT_EXTEND | ADMIN:{user_id} | "
        f"USER:{target_user_id} | CONFIG:{config_hash[:20] if config_hash else 'unknown'}"
    )
