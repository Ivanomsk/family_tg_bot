import pytest
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from handlers.proxy import router


@pytest.mark.asyncio
class TestProxyHandler:
    """Тесты для handlers/proxy.py"""
    
    async def test_cmd_request_proxy_private(self, mock_message, mock_bot):
        """Тест запроса прокси в ЛС"""
        from handlers.proxy import cmd_request_proxy
        
        mock_message.chat.type = "private"
        mock_message.text = "/request_proxy"
        
        with patch('handlers.proxy.is_rate_limited', return_value=(False, 0)):
            await cmd_request_proxy(mock_message)
        
        mock_message.answer.assert_called()
    
    async def test_cmd_request_proxy_group(self, mock_message, mock_bot):
        """Тест запроса прокси в группе"""
        from handlers.proxy import cmd_request_proxy
        
        mock_message.chat.type = "group"
        mock_message.text = "/request_proxy"
        
        await cmd_request_proxy(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "только в личных сообщениях" in call_args[0][0]
    
    async def test_cmd_my_proxy_no_proxies(self, mock_message, mock_bot):
        """Тест просмотра прокси без прокси"""
        from handlers.proxy import cmd_my_proxy
        
        mock_message.chat.type = "private"
        mock_message.text = "/my_proxy"
        
        with patch('handlers.proxy.load_json', return_value={}):
            with patch('handlers.proxy.is_rate_limited', return_value=(False, 0)):
                await cmd_my_proxy(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "пока нет прокси" in call_args[0][0]
    
    async def test_format_proxy_card(self):
        """Тест форматирования карточки прокси"""
        from handlers.proxy import format_proxy_card
        
        card = format_proxy_card("Test", "server.com", 443, "secret123")
        
        assert "Test" in card
        assert "server.com" in card
        assert "443" in card
        assert "secret123" in card
    
    async def test_format_proxy_card_with_button(self):
        """Тест форматирования карточки с кнопкой"""
        from handlers.proxy import format_proxy_card_with_button
        
        text, tg_link = format_proxy_card_with_button("Test", "server.com", 443, "secret123")
        
        assert "Test" in text
        assert "tg://proxy" in tg_link
        assert "server.com" in tg_link
