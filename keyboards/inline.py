from aiogram.utils.keyboard import InlineKeyboardBuilder

# ==========================================
# ГЛАВНОЕ МЕНЮ
# ==========================================

def get_main_menu_keyboard(is_admin: bool = False) -> InlineKeyboardBuilder:
    """Клавиатура главного меню"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🔐 VPN", callback_data="menu_vpn")
    builder.button(text="🛰 Прокси", callback_data="menu_proxy_main")
    builder.button(text="📖 Помощь", callback_data="menu_help")
    builder.button(text="🏓 Проверка связи", callback_data="menu_ping")
    
    if is_admin:
        builder.button(text="⚙️ Админ-панель", callback_data="menu_admin_main")
    
    if is_admin:
        builder.adjust(2, 1, 1)
    else:
        builder.adjust(2, 1)
    
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

def get_vpn_main_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура раздела VPN"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Мои конфиги", callback_data="show_my_configs")
    builder.button(text="📥 Запросить новый", callback_data="vpn_request")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(1)
    return builder


def get_vpn_list_keyboard(configs: list, username: str) -> InlineKeyboardBuilder:
    """Список VPN конфигов с индикаторами"""
    from utils.expiry import get_vpn_config_age
    
    builder = InlineKeyboardBuilder()
    
    for i, conf in enumerate(configs):
        age = get_vpn_config_age(username, conf)
        
        if age["status"] == "expired":
            emoji = "🔴"
            suffix = " (истёк)"
        elif age["status"] == "expiring_soon":
            emoji = "🟡"
            suffix = f" ({age['days_left']} дн.)"
        else:
            emoji = "🟢"
            suffix = ""
        
        btn_text = f"{emoji} {conf.replace('.vpn', '')}{suffix}"
        builder.button(text=btn_text, callback_data=f"vpn_select_{i}")
    
    builder.button(text="📥 Запросить новый", callback_data="vpn_request")
    builder.button(text="🔙 Назад", callback_data="menu_vpn_main")
    builder.adjust(1)
    return builder


def get_vpn_empty_keyboard() -> InlineKeyboardBuilder:
    """Меню когда нет VPN конфигов"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Запросить новый", callback_data="vpn_request")
    builder.button(text="🔙 Назад", callback_data="menu_vpn_main")
    builder.adjust(1)
    return builder


def get_vpn_request_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура запроса VPN (для пользователя)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="menu_vpn_main")
    builder.adjust(1)
    return builder


# ==========================================
# ПРОКСИ МЕНЮ
# ==========================================

def get_proxy_main_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура раздела Прокси"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Мои прокси", callback_data="menu_proxy")
    builder.button(text="📥 Запросить новый", callback_data="proxy_request")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(1)
    return builder


def get_proxy_list_keyboard(proxies: list, user_id: int) -> InlineKeyboardBuilder:
    """Список прокси с индикаторами"""
    from utils.expiry import get_proxy_age
    
    builder = InlineKeyboardBuilder()
    
    for i, proxy in enumerate(proxies):
        age = get_proxy_age(user_id, proxy["name"])
        
        if age["status"] == "expired":
            emoji = "🔴"
            suffix = " (истёк)"
        elif age["status"] == "expiring_soon":
            emoji = "🟡"
            suffix = f" ({age['days_left']} дн.)"
        else:
            emoji = "🟢"
            suffix = ""
        
        btn_text = f"{emoji} {proxy['name']}{suffix}"
        builder.button(text=btn_text, callback_data=f"proxy_select_{i}")
    
    builder.button(text="📥 Запросить новый", callback_data="proxy_request")
    builder.button(text="🔙 Назад", callback_data="menu_proxy_main")
    builder.adjust(1)
    return builder


def get_proxy_empty_keyboard() -> InlineKeyboardBuilder:
    """Меню когда нет прокси"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📥 Запросить прокси", callback_data="proxy_request")
    builder.button(text="🔙 Назад", callback_data="menu_proxy_main")
    builder.adjust(1)
    return builder


def get_proxy_detail_keyboard(tg_link: str, is_expired: bool = False) -> InlineKeyboardBuilder:
    """Карточка прокси с кнопкой подключения"""
    builder = InlineKeyboardBuilder()
    
    if not is_expired and tg_link:
        builder.button(text="📱 Подключить в Telegram", url=tg_link)
    
    builder.button(text="🔙 Назад к списку", callback_data="menu_proxy")
    builder.button(text="🔙 Назад в меню", callback_data="menu_main")
    builder.adjust(1)
    return builder


def get_proxy_request_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура запроса прокси (для пользователя)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Отмена", callback_data="menu_proxy_main")
    builder.adjust(1)
    return builder


def get_proxy_list_keyboard_compat(proxies: list) -> InlineKeyboardBuilder:
    """Список прокси без user_id (для обратной совместимости с proxy.py)"""
    builder = InlineKeyboardBuilder()
    for i, proxy in enumerate(proxies):
        builder.button(text=f"🟢 {proxy['name']}", callback_data=f"proxy_show_{i}")
    builder.adjust(1)
    return builder


# ==========================================
# ПОМОЩЬ (СПРАВОЧНИК)
# ==========================================

def get_help_main_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура раздела Помощь"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📖 Как получить VPN", callback_data="help_vpn_how")
    builder.button(text="📖 Как запросить прокси", callback_data="help_proxy_how")
    builder.button(text="📖 Как подключить прокси", callback_data="help_proxy_connect")
    builder.button(text="📝 Сообщить о проблеме", callback_data="problem_start")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    
    builder.adjust(1)
    return builder


# ==========================================
# АДМИН-ПАНЕЛЬ
# ==========================================

def get_admin_main_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура админ-панели"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="menu_stats")
    builder.button(text="🔍 Проверка сроков", callback_data="admin_check_expiry")
    builder.button(text="👥 Управление пользователями", callback_data="admin_users")
    builder.button(text="📦 Бэкапы", callback_data="menu_backup")
    builder.button(text="📢 Опубликовать новость", callback_data="news_start")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(1)
    return builder


def get_admin_users_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура управления пользователями"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Список VPN", callback_data="admin_vpn_list")
    builder.button(text="🗑️ Отозвать VPN", callback_data="admin_vpn_revoke")
    builder.button(text="📋 Список прокси", callback_data="admin_proxy_list")
    builder.button(text="♾️ Бессрочный статус", callback_data="admin_permanent_menu")
    builder.button(text="🔙 Назад", callback_data="menu_admin_main")
    builder.adjust(1)
    return builder


def get_back_keyboard(callback: str) -> InlineKeyboardBuilder:
    """Универсальная кнопка Назад"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data=callback)
    builder.adjust(1)
    return builder


# ==========================================
# КОНФИГИ (ДЕТАЛИ)
# ==========================================

def get_config_detail_keyboard(user_id: int, config_hash: str, days_left: int) -> InlineKeyboardBuilder:
    """Клавиатура для активного конфига"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="🔄 Запросить продление",
        callback_data=f"request_extend_{user_id}_{config_hash}"
    )
    
    builder.button(
        text="🔙 К списку",
        callback_data="show_my_configs"
    )
    builder.button(
        text="🔙 Назад в меню",
        callback_data="menu_main"
    )
    builder.adjust(1)
    return builder


def get_config_detail_keyboard_expired(user_id: int, config_hash: str) -> InlineKeyboardBuilder:
    """Клавиатура для истекшего конфига (без скачивания)"""
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="🔄 Запросить продление",
        callback_data=f"request_extend_{user_id}_{config_hash}"
    )
    
    builder.button(
        text="🔙 К списку",
        callback_data="show_my_configs"
    )
    builder.button(
        text="🔙 Назад в меню",
        callback_data="menu_main"
    )
    builder.adjust(1)
    return builder


def get_my_configs_keyboard(user_id: int, configs: list) -> InlineKeyboardBuilder:
    """Клавиатура со списком конфигов пользователя"""
    builder = InlineKeyboardBuilder()
    
    for config in configs:
        days_left = config.get('days_left', 0)
        if days_left is not None and days_left < 0:
            status = "🔴"
        elif days_left is not None and days_left <= 3:
            status = "🟡"
        else:
            status = "🟢"
        
        btn_text = f"{status} {config.get('username', 'unknown')}"
        builder.button(
            text=btn_text,
            callback_data=f"my_config_{user_id}_{config.get('hash')}"
        )
    
    builder.button(
        text="🔄 Обновить",
        callback_data="refresh_my_configs"
    )
    builder.button(
        text="🔙 Назад",
        callback_data="menu_vpn_main"
    )
    builder.adjust(1)
    return builder


def get_extend_success_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура после успешного продления"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="📋 Мои конфиги",
        callback_data="show_my_configs"
    )
    builder.button(
        text="🔙 В главное меню",
        callback_data="menu_main"
    )
    builder.adjust(1)
    return builder


# ==========================================
# НОВОСТИ
# ==========================================

def get_news_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура для выбора типа новости"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📰 Обычная новость", callback_data="news_type_regular")
    builder.button(text="📢 Анонс обновления Amnezia VPN", callback_data="news_type_amnezia")
    builder.button(text="❌ Отмена", callback_data="news_cancel")
    builder.adjust(1)
    return builder


def get_news_confirm_keyboard():
    """Клавиатура подтверждения публикации"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Опубликовать", callback_data="news_confirm_publish")
    builder.button(text="❌ Отмена", callback_data="news_cancel")
    builder.adjust(2)
    return builder.as_markup()


def get_amnezia_announce_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура для анонса обновления Amnezia VPN"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Опубликовать в чат", callback_data="amnezia_publish")
    builder.button(text="🔙 Назад", callback_data="menu_admin_main")
    builder.adjust(1)
    return builder


# ==========================================
# АДМИНСКИЕ ЗАПРОСЫ (VPN и ПРОКСИ)
# ==========================================

def get_admin_vpn_request_keyboard(user_id: int) -> InlineKeyboardBuilder:
    """Клавиатура запроса VPN для админа - автоматическая генерация"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Выпустить автоматически", callback_data=f"vpn_req_auto_{user_id}")
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


def get_admin_extend_request_keyboard(user_id: int, config_hash: str) -> InlineKeyboardBuilder:
    """Клавиатура для админа — одобрить/отклонить продление"""
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Одобрить",
        callback_data=f"approve_extend_{user_id}_{config_hash}"
    )
    builder.button(
        text="❌ Отклонить",
        callback_data=f"reject_extend_{user_id}_{config_hash}"
    )
    builder.adjust(2)
    return builder


# ==========================================
# АЛИАСЫ ДЛЯ СТАРЫХ ИМПОРТОВ (ОБРАТНАЯ СОВМЕСТИМОСТЬ)
# ==========================================

def get_help_keyboard(is_admin: bool = False) -> InlineKeyboardBuilder:
    """Клавиатура справки (для обратной совместимости)"""
    builder = InlineKeyboardBuilder()
    if is_admin:
        builder.button(text="📊 Показать статистику", callback_data="menu_stats")
    builder.button(text="🔙 Назад", callback_data="menu_main")
    builder.adjust(1)
    return builder


def get_problem_report_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура для отчёта о проблеме (для обратной совместимости)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Написать о проблеме", callback_data="problem_start")
    builder.button(text="🔙 Назад к справке", callback_data="menu_help")
    builder.adjust(1)
    return builder


def get_problem_cancel_keyboard() -> InlineKeyboardBuilder:
    """Клавиатура отмены репорта/новости (для обратной совместимости)"""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_action")
    builder.adjust(1)
    return builder


def get_proxy_card_keyboard(tg_link: str) -> InlineKeyboardBuilder:
    """Алиас для get_proxy_detail_keyboard (для обратной совместимости)"""
    return get_proxy_detail_keyboard(tg_link)
