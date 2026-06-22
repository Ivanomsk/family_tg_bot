from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Возвращает клавиатуру с кнопками VPN и Прокси"""
    buttons = [
        [KeyboardButton(text="🔐 VPN"), KeyboardButton(text="🌐 Прокси")]  # 2 кнопки в ряд
    ]
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,   # Клавиатура подстраивается под размер экрана
        one_time_keyboard=False # Остаётся после нажатия
    )
