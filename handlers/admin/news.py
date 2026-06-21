from aiogram import Router, F, types
from config import ADMIN_IDS
from keyboards.inline import (
    get_news_keyboard,
    get_amnezia_announce_keyboard,
    get_admin_main_keyboard,
)
router = Router()
@router.callback_query(F.data == "news_start")
async def news_start(callback: types.CallbackQuery):
    """Публикация новости"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    await callback.message.edit_text(
        "📢 <b>Публикация новости</b>\n\nВыберите тип новости:",
        parse_mode="HTML",
        reply_markup=get_news_keyboard().as_markup()
    )


@router.callback_query(F.data == "news_type_regular")
async def news_type_regular(callback: types.CallbackQuery):
    """Обычная новость"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    await callback.answer()
    
    await callback.message.edit_text(
        "📰 <b>Обычная новость</b>\n\n"
        "Отправьте текст новости.\n"
        "Поддерживается HTML-разметка.\n\n"
        "Пример:\n"
        "<code>&lt;b&gt;Важная новость!&lt;/b&gt;\n"
        "Текст новости с &lt;a href=&quot;https://example.com&quot;&gt;ссылкой&lt;/a&gt;.</code>\n\n"
        "Для отмены отправьте /cancel",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "news_type_amnezia")
async def news_type_amnezia(callback: types.CallbackQuery):
    """Анонс обновления Amnezia VPN"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    text = (
        "<b>📢 Обновление Amnezia VPN</b>\n\n"
        "Доступна новая версия клиента для всех платформ.\n\n"
        "<b>Для ПК:</b>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN_x64.exe'>Windows</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN.dmg'>macOS (Intel)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN-arm64.dmg'>macOS (Apple Silicon)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN_Linux.deb'>Linux</a>\n\n"
        "<b>Для мобильных:</b>\n"
        "• <a href='https://play.google.com/store/apps/details?id=org.amnezia.vpn'>Android (Google Play)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN.apk'>Android (APK с GitHub)</a>\n"
        "• <a href='https://apps.apple.com/app/amneziavpn/id1600529900'>iOS (App Store)</a>\n\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest'>Все версии на GitHub</a>\n\n"
        "<b>Важно:</b> если вы меняете источник установки, может возникнуть ошибка."
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_amnezia_announce_keyboard().as_markup(),
        disable_web_page_preview=False
    )
    await callback.answer()


@router.callback_query(F.data == "amnezia_publish")
async def amnezia_publish(callback: types.CallbackQuery):
    """Опубликовать анонс обновления в чат"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return
    
    from config import ALLOWED_CHAT_ID
    
    text = (
        "<b>📢 Обновление Amnezia VPN</b>\n\n"
        "Доступна новая версия клиента для всех платформ.\n\n"
        "<b>Для ПК:</b>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN_x64.exe'>Windows</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN.dmg'>macOS (Intel)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN-arm64.dmg'>macOS (Apple Silicon)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN_Linux.deb'>Linux</a>\n\n"
        "<b>Для мобильных:</b>\n"
        "• <a href='https://play.google.com/store/apps/details?id=org.amnezia.vpn'>Android (Google Play)</a>\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN.apk'>Android (APK с GitHub)</a>\n"
        "• <a href='https://apps.apple.com/app/amneziavpn/id1600529900'>iOS (App Store)</a>\n\n"
        "• <a href='https://github.com/amnezia-vpn/amnezia-client/releases/latest'>Все версии на GitHub</a>\n\n"
        "<b>Важно:</b> если вы меняете источник установки, может возникнуть ошибка."
    )
    
    try:
        await callback.bot.send_message(
            ALLOWED_CHAT_ID,
            text,
            parse_mode="HTML",
            disable_web_page_preview=False
        )
        await callback.answer("✅ Анонс опубликован в чате!", show_alert=True)
        await callback.message.edit_text(
            "⚙️ <b>Админ-панель</b>\n\nАнонс успешно опубликован!",
            parse_mode="HTML",
            reply_markup=get_admin_main_keyboard().as_markup()
        )
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


