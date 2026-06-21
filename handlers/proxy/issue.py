from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS
from states.forms import ProxyIssue

router = Router()

# ==========================================
# ПРОКСИ - АДМИН (ВЫДАЧА/ОТКЛОНЕНИЕ)
# ==========================================

@router.callback_query(F.data.startswith("proxy_issue_"))
async def proxy_issue(callback: types.CallbackQuery, state: FSMContext):
    """Админ начинает выдачу прокси — запрашиваем имя"""
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[-1])
    
    await state.update_data(target_user_id=user_id)
    await state.set_state(ProxyIssue.waiting_for_name)
    
    await callback.message.edit_text(
        "📝 <b>Введите название прокси</b>\n\n"
        "Например: Основной, Резерв, Для работы и т.д.\n\n"
        "Или нажмите /cancel для отмены.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(ProxyIssue.waiting_for_name, F.text)
async def proxy_issue_get_name(message: types.Message, state: FSMContext):
    """Получаем имя прокси, запрашиваем ключ"""
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_back_to_main_menu().as_markup())
        return
    
    name = message.text.strip()
    await state.update_data(proxy_name=name)
    await state.set_state(ProxyIssue.waiting_for_key)
    
    await message.answer(
        "🔑 <b>Введите ключ прокси</b>\n\n"
        "Вставьте ссылку в формате:\n"
        "<code>tg://proxy?server=nas-msk.online&port=443&secret=eec03592318ff9f161f29538302627ebfd6e61732d6d736b2e6f6e6c696e65</code>\n\n"
        "Или нажмите /cancel для отмены.",
        parse_mode="HTML"
    )

@router.message(ProxyIssue.waiting_for_key, F.text)
async def proxy_issue_get_key(message: types.Message, state: FSMContext):
    """Получаем ключ и сохраняем прокси"""
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Отменено.", reply_markup=get_back_to_main_menu().as_markup())
        return
    
    key_text = message.text.strip()
    
    # Проверяем формат tg://proxy
    if not key_text.startswith('tg://proxy'):
        await message.answer(
            "❌ <b>Неверный формат!</b>\n\n"
            "Ссылка должна начинаться с <code>tg://proxy</code>\n\n"
            "Пример:\n"
            "<code>tg://proxy?server=nas-msk.online&port=443&secret=eec03592318ff9f161f29538302627ebfd6e61732d6d736b2e6f6e6c696e65</code>",
            parse_mode="HTML"
        )
        return
    
    # Парсим параметры
    parsed = urllib.parse.urlparse(key_text)
    params = urllib.parse.parse_qs(parsed.query)
    
    server = params.get('server', [None])[0]
    port = params.get('port', [None])[0]
    secret = params.get('secret', [None])[0]
    
    if not server or not port or not secret:
        await message.answer(
            "❌ <b>Не хватает параметров!</b>\n\n"
            "Должны быть: <code>server</code>, <code>port</code>, <code>secret</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        port = int(port)
    except ValueError:
        await message.answer("❌ Порт должен быть числом.")
        return
    
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    proxy_name = data.get('proxy_name', 'Прокси')
    
    user_proxies = load_json(USER_PROXIES_FILE, {})
    user_id_str = str(target_user_id)
    
    if user_id_str not in user_proxies:
        user_proxies[user_id_str] = {"proxies": []}
    
    proxy_data = {
        "name": proxy_name,
        "server": server,
        "port": port,
        "secret": secret,
        "issued_at": datetime.now().isoformat(),
        "issued_by": message.from_user.id
    }
    
    user_proxies[user_id_str]["proxies"].append(proxy_data)
    save_json(USER_PROXIES_FILE, user_proxies)
    
    tg_link = f"tg://proxy?server={server}&port={port}&secret={secret}"
    
    try:
        await message.bot.send_message(
            target_user_id,
            f"✅ <b>Ваш персональный прокси готов!</b>\n\n"
            f"📁 <b>Имя:</b> {proxy_name}\n"
            f"🌐 <b>Сервер:</b> {server}\n"
            f"🔌 <b>Порт:</b> {port}\n"
            f"📅 <b>Выдан:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
            f"💡 Нажмите кнопку для подключения:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📱 Подключить в Telegram", url=tg_link)]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки прокси пользователю {target_user_id}: {e}")
        await message.answer(f"❌ Ошибка отправки пользователю: {e}")
        await state.clear()
        return
    
    await message.answer(
        f"✅ <b>Прокси выдан!</b>\n\n"
        f"👤 Пользователь: ID {target_user_id}\n"
        f"📁 Имя: {proxy_name}\n"
        f"🌐 Сервер: {server}\n"
        f"🔌 Порт: {port}\n\n"
        f"💡 Пользователь получил уведомление.",
        reply_markup=get_back_to_main_menu().as_markup(),
        parse_mode="HTML"
    )
    
    audit_logger.info(f"ACTION:PROXY_ISSUED | ADMIN:{message.from_user.id} | USER:{target_user_id} | NAME:{proxy_name}")
    await state.clear()

