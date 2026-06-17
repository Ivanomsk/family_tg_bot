import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from keyboards.inline import (
    get_main_menu_keyboard,
    get_back_to_main_menu,
    get_vpn_list_keyboard,
    get_vpn_empty_keyboard,
    get_proxy_list_keyboard,
    get_proxy_detail_keyboard,
    get_help_keyboard
)


class TestKeyboards:
    """Тесты для клавиатур"""
    
    def test_main_menu_keyboard_user(self):
        """Тест главного меню для пользователя"""
        keyboard = get_main_menu_keyboard(is_admin=False)
        markup = keyboard.as_markup()
        
        assert len(markup.inline_keyboard) > 0
        
        button_texts = [btn.text for row in markup.inline_keyboard for btn in row]
        assert "🔐 VPN конфиги" in button_texts
        assert "🛰 Мои прокси" in button_texts
        assert "📖 Справка" in button_texts
        assert "🏓 Проверка связи" in button_texts
    
    def test_main_menu_keyboard_admin(self):
        """Тест главного меню для админа"""
        keyboard = get_main_menu_keyboard(is_admin=True)
        markup = keyboard.as_markup()
        
        button_texts = [btn.text for row in markup.inline_keyboard for btn in row]
        assert "⚙️ Администрирование" in button_texts
        assert "📢 Опубликовать новость" in button_texts
    
    def test_back_to_main_menu(self):
        """Тест кнопки назад"""
        keyboard = get_back_to_main_menu()
        markup = keyboard.as_markup()
        
        assert len(markup.inline_keyboard) == 1
        assert markup.inline_keyboard[0][0].text == "🔙 Назад в главное меню"
    
    def test_vpn_empty_keyboard(self):
        """Тест пустого VPN меню"""
        keyboard = get_vpn_empty_keyboard()
        markup = keyboard.as_markup()
        
        button_texts = [btn.text for row in markup.inline_keyboard for btn in row]
        assert "🔄 Запросить новый конфиг" in button_texts
        assert "🔙 Назад" in button_texts
    
    def test_proxy_detail_keyboard(self):
        """Тест клавиатуры деталей прокси"""
        tg_link = "tg://proxy?server=test&port=443&secret=123"
        keyboard = get_proxy_detail_keyboard(tg_link)
        markup = keyboard.as_markup()
        
        button_texts = [btn.text for row in markup.inline_keyboard for btn in row]
        assert "📱 Подключить в Telegram" in button_texts
        assert "🔙 Назад к списку" in button_texts
    
    def test_vpn_list_keyboard(self):
        """Тест списка VPN конфигов"""
        configs = ["test1.vpn", "test2.vpn"]
        keyboard = get_vpn_list_keyboard(configs, "test_user")
        markup = keyboard.as_markup()
        
        assert len(markup.inline_keyboard) > 0
    
    def test_proxy_list_keyboard(self):
        """Тест списка прокси"""
        proxies = [
            {"name": "proxy1", "server": "test", "port": 443, "secret": "123"}
        ]
        keyboard = get_proxy_list_keyboard(proxies, 123456)
        markup = keyboard.as_markup()
        
        assert len(markup.inline_keyboard) > 0
    
    def test_help_keyboard(self):
        """Тест клавиатуры справки"""
        keyboard = get_help_keyboard(is_admin=False)
        markup = keyboard.as_markup()
        
        assert len(markup.inline_keyboard) > 0