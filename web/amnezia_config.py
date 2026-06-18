"""Конфигурация для публикаций об обновлениях Amnezia VPN"""

# Актуальные ссылки на июнь 2026
# GitHub использует /releases/latest для автоматического редиректа на последнюю версию
AMNEZIA_LINKS = {
    "github_releases": "https://github.com/amnezia-vpn/amnezia-client/releases/latest",
    
    # ПК версии
    "windows": "https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN_x64.exe",
    "macos_intel": "https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN.dmg",
    "macos_apple_silicon": "https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN-arm64.dmg",
    "linux": "https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN_Linux.deb",
    
    # Мобильные версии
    "google_play": "https://play.google.com/store/apps/details?id=org.amnezia.vpn",
    "apk_github": "https://github.com/amnezia-vpn/amnezia-client/releases/latest/download/AmneziaVPN.apk",
    "app_store": "https://apps.apple.com/app/amneziavpn/id1600529900",
}

# Предупреждение о конфликте версий
VERSION_CONFLICT_WARNING = (
    "⚠️ <b>Важно:</b> если вы меняете источник установки "
    "(например, раньше скачивали приложение с GitHub, а теперь обновляете через Google Play), "
    "может возникнуть ошибка. Чтобы избежать конфликта версий, используйте один и тот же источник. "
    "Если ошибка все же появилась, удалите старую версию и установите приложение заново."
)

# Универсальный шаблон для всех платформ
UNIVERSAL_TEMPLATE = {
    "title": "🆕 <b>Обновление Amnezia VPN</b>",
    "body": "Доступна новая версия клиента для всех платформ.",
    "links_section": (
        " <b>Для ПК:</b>\n"
        "🪟 <a href='{windows}'>Windows</a>\n"
        "🍎 <a href='{macos_intel}'>macOS (Intel)</a>\n"
        "💻 <a href='{macos_apple_silicon}'>macOS (Apple Silicon)</a>\n"
        "🐧 <a href='{linux}'>Linux</a>\n\n"
        " <b>Для мобильных:</b>\n"
        "🤖 <a href='{google_play}'>Android (Google Play)</a>\n"
        "📦 <a href='{apk_github}'>Android (APK с GitHub)</a>\n"
        "🍎 <a href='{app_store}'>iOS (App Store)</a>\n\n"
        "🔗 <a href='{github_releases}'>Все версии на GitHub</a>"
    ),
    "buttons": [
        [
            {"text": "🪟 Windows", "url": "windows"},
            {"text": "🍎 macOS Intel", "url": "macos_intel"},
            {"text": "💻 macOS M1/M2/M3", "url": "macos_apple_silicon"},
        ],
        [
            {"text": "🐧 Linux", "url": "linux"},
            {"text": "🤖 Google Play", "url": "google_play"},
            {"text": "📦 APK GitHub", "url": "apk_github"},
        ],
        [
            {"text": "🍎 App Store", "url": "app_store"},
            {"text": "🔗 GitHub Releases", "url": "github_releases"},
        ],
    ],
}