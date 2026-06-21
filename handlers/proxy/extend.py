from aiogram import Router, F, types

router = Router()

# ==========================================
# ПРОДЛЕНИЕ ПРОКСИ
# ==========================================

@router.callback_query(F.data.startswith("proxy_extend_"))
async def proxy_extend_request(callback: types.CallbackQuery):
    if not await require_private_chat(callback, "запрос продления"):
        return
    
    await callback.answer()
    
    parts = callback.data.split("_")
    if len(parts) < 3:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        user_id = int(parts[1])
        proxy_index = int(parts[2])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    if callback.from_user.id != user_id:
        await callback.answer("⛔ Это не ваш прокси!", show_alert=True)
        return
    
    user_proxies = load_json(USER_PROXIES_FILE, {})
    proxies = user_proxies.get(str(user_id), {}).get("proxies", [])
    
    if proxy_index >= len(proxies):
        await callback.answer("❌ Прокси не найден", show_alert=True)
        return
    
    proxy = proxies[proxy_index]
    username = callback.from_user.username or f"ID:{user_id}"
    user_mention = f"@{username}" if callback.from_user.username else f"ID:{user_id}"
    
    admin_text = (
        f"🔄 <b>Запрос на продление прокси</b>\n\n"
        f"👤 <b>Пользователь:</b> {user_mention}\n"
        f"📁 <b>Имя:</b> {proxy['name']}\n"
        f"🌐 <b>Сервер:</b> {proxy['server']}\n"
        f"📅 <b>Выдан:</b> {proxy.get('issued_at', 'не указана')}\n\n"
        f"Действия:"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить продление",
                callback_data=f"proxy_approve_extend_{user_id}_{proxy_index}"
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=f"proxy_reject_extend_{user_id}_{proxy_index}"
            )
        ]
    ])
    
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                admin_text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить запрос админу {admin_id}: {e}")
    
    await callback.answer("✅ Запрос на продление отправлен администратору!")
    await callback.message.edit_text(
        "🔄 <b>Запрос на продление отправлен!</b>\n\n"
        "Администратор рассмотрит ваш запрос в ближайшее время.\n"
        "Вы получите уведомление о решении.",
        parse_mode="HTML",
        reply_markup=get_back_keyboard("menu_proxy").as_markup()
    )
    
    audit_logger.info(
        f"ACTION:PROXY_EXTEND_REQUEST | USER:{user_id} | "
        f"PROXY:{proxy['name']} | INDEX:{proxy_index}"
    )


@router.callback_query(F.data.startswith("proxy_approve_extend_"))
async def proxy_approve_extend(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        target_user_id = int(parts[2])
        proxy_index = int(parts[3])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_proxies = load_json(USER_PROXIES_FILE, {})
    proxies = user_proxies.get(str(target_user_id), {}).get("proxies", [])
    
    if proxy_index >= len(proxies):
        await callback.answer("❌ Прокси не найден", show_alert=True)
        return
    
    proxies[proxy_index]['issued_at'] = datetime.now().isoformat()
    user_proxies[str(target_user_id)]["proxies"] = proxies
    save_json(USER_PROXIES_FILE, user_proxies)
    
    try:
        await callback.bot.send_message(
            target_user_id,
            f"✅ <b>Ваш запрос на продление прокси одобрен!</b>\n\n"
            f"📁 <b>Прокси:</b> {proxies[proxy_index]['name']}\n"
            f"📅 <b>Новая дата выдачи:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"💡 Прокси продлён на 30 дней.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось уведомить пользователя {target_user_id}: {e}")
    
    await callback.answer("✅ Прокси продлён на 30 дней!")
    await callback.message.edit_text(
        f"✅ <b>Продление одобрено!</b>\n\n"
        f"👤 Пользователь получил уведомление.\n"
        f"📁 Прокси: {proxies[proxy_index]['name']}",
        parse_mode="HTML"
    )
    
    audit_logger.info(
        f"ACTION:PROXY_APPROVE_EXTEND | ADMIN:{user_id} | "
        f"USER:{target_user_id} | PROXY:{proxies[proxy_index]['name']}"
    )


@router.callback_query(F.data.startswith("proxy_reject_extend_"))
async def proxy_reject_extend(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    parts = callback.data.split("_")
    if len(parts) < 4:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    try:
        target_user_id = int(parts[2])
        proxy_index = int(parts[3])
    except ValueError:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_proxies = load_json(USER_PROXIES_FILE, {})
    proxies = user_proxies.get(str(target_user_id), {}).get("proxies", [])
    proxy_name = proxies[proxy_index]['name'] if proxy_index < len(proxies) else "неизвестный"
    
    try:
        await callback.bot.send_message(
            target_user_id,
            f"❌ <b>Ваш запрос на продление прокси отклонён</b>\n\n"
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
        f"📁 Прокси: {proxy_name}",
        parse_mode="HTML"
    )
    
    audit_logger.info(
        f"ACTION:PROXY_REJECT_EXTEND | ADMIN:{user_id} | "
        f"USER:{target_user_id} | PROXY:{proxy_name}"
    )
