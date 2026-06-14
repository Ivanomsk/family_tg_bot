from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==========================================
# ГЛАВНОЕ МЕНЮ
# ==========================================

def get_main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardBuilder:
    """Клавиатура главного меню"""
    builder = InlineKeyboardBuilder()
    
    # Основные кнопки (4 штуки)
    builder.button(text="🔐 VPN конфиги", callback_data="menu_vpn")
    builder.button(text="🛰 Мои прокси", callback_data="menu_proxy")
    builder.button(text="📖 Справка", callback_data="menu_help")
    builder.button(text="🏓 Проверка связи", callback_data="menu_ping")
    
    # Админка (отдельно)
    if is_admin:
        builder.button(text="⚙️ Администрирование", callback_data="menu_admin")
        # 2 кнопки в ряд, потом 2 кнопки в ряд, потом 1 кнопка
        builder.adjust(2, 2, 1)
    else:
        # 2 кнопки в ряд, потом 2 кнопки в ряд
        builder.adjust(2, 2)
    
    return builder


def get_back_to_main_menu() -> InlineKeyboardBuilder:
    """Кнопка возврата в главное меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад в главное меню", callback_data="menu_main")
    builder.adjust(1)
    return builder


# ==========================================
# VPN МЕНЮ
# ==========================================

def get_vpn_list_keyboard(configs: list, username: str) -> InlineKeyboardBuilder:
    """Список VPN конфигов с индикаторами"""
    from utils.expiry import get_vpn_config_age
    
    builder = InlineKeyboardBuilder()
    
    for i, conf in enumerate(configs):
        age = get_vpn_config_age(username, conf)
        
        if age["status"] == "expired":
            emoji = ""
            suffix = " (истёк)"
        elif age["status"] == "expiring_soon":
            emoji = "⚠️"
            suffix = f" ({age['days_left']} дн.)"
        else:
            emoji = "🔹"
            suffix = ""
        
        btn_text = f"{emoji} {conf.replace('.vpn', '')}{suffix}"
        builder.button(text=btn_text, callback_data=f"vpn_select_{i}")
    
    if configs:
        builder.button(text="📦 Отправить все", callback_data="vpn_send_all")
    
    builder.button(text=" Запросить новый конфиг", callback_data="vpn_request")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(1)
    return builder


def get_vpn_empty_keyboard() -> InlineKeyboardBuilder:
    """Меню когда нет VPN конфигов"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Запросить новый конфиг", callback_data="vpn_request")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(1)
    return builder


def get_vpn_request_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура запроса VPN (для пользователя)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="menu_vpn")
    builder.adjust(1)
    return builder


# ==========================================
# ПРОКСИ МЕНЮ
# ==========================================

def get_proxy_list_keyboard(proxies: list, user_id: int) -> InlineKeyboardBuilder:
    """Список прокси с индикаторами (для нового меню)"""
    from utils.expiry import get_proxy_age
    
    builder = InlineKeyboardBuilder()
    
    for i, proxy in enumerate(proxies):
        age = get_proxy_age(user_id, proxy["name"])
        
        if age["status"] == "expired":
            emoji = "❌"
            suffix = " (истёк)"
        elif age["status"] == "expiring_soon":
            emoji = "⚠️"
            suffix = f" ({age['days_left']} дн.)"
        else:
            emoji = "🔹"
            suffix = ""
        
        btn_text = f"{emoji} {proxy['name']}{suffix}"
        builder.button(text=btn_text, callback_data=f"proxy_select_{i}")
    
    builder.button(text="🛰 Запросить новый прокси", callback_data="proxy_request")
    builder.button(text=" Назад", callback_data="menu_main")
    builder.adjust(1)
    return builder


def get_proxy_list_keyboard_compat(proxies: list) -> InlineKeyboardBuilder:
    """Список прокси без user_id (для обратной совместимости с proxy.py)"""
    builder = InlineKeyboardBuilder()
    for i, proxy in enumerate(proxies):
        builder.button(text=f"🔹 {proxy['name']}", callback_data=f"proxy_show_{i}")
    builder.adjust(1)
    return builder


def get_proxy_detail_keyboard(tg_link: str) -> InlineKeyboardBuilder:
    """Карточка прокси с кнопкой подключения"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Подключить в Telegram", url=tg_link)
    builder.button(text="🔙 Назад к списку", callback_data="menu_proxy")
    builder.adjust(1)
    return builder


def get_proxy_card_keyboard(tg_link: str) -> InlineKeyboardBuilder:
    """Алиас для get_proxy_detail_keyboard (для обратной совместимости)"""
    return get_proxy_detail_keyboard(tg_link)


def get_proxy_empty_keyboard() -> InlineKeyboardBuilder:
    """Меню когда нет прокси"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🛰 Запросить прокси", callback_data="proxy_request")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(1)
    return builder


def get_proxy_request_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура запроса прокси (для пользователя)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="menu_proxy")
    builder.adjust(1)
    return builder


# ==========================================
# СПРАВКА И АДМИНКА
# ==========================================

def get_help_keyboard(is_admin: bool = False) -> InlineKeyboardBuilder:
    """Клавиатура справки"""
    builder = InlineKeyboardBuilder()
    if is_admin:
        builder.button(text="📊 Показать статистику", callback_data="menu_stats")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(1)
    return builder


# ==========================================
# АДМИНСКИЕ КЛАВИАТУРЫ (для handlers/vpn.py и proxy.py)
# ==========================================

def get_admin_vpn_request_keyboard(user_id: int) -> InlineKeyboardBuilder:
    """Клавиатура запроса VPN для админа"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Загрузить файл", callback_data=f"vpn_req_upload_{user_id}")
    builder.button(text="❌ Отклонить", callback_data=f"vpn_req_reject_{user_id}")
    builder.adjust(1)
    return builder


def get_admin_proxy_request_keyboard(user_id: int) -> InlineKeyboardBuilder:
    """Клавиатура запроса прокси для админа"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Выписать ключ", callback_data=f"proxy_req_issue_{user_id}")
    builder.button(text="❌ Отклонить", callback_data=f"proxy_req_reject_{user_id}")
    builder.adjust(1)
    return builder