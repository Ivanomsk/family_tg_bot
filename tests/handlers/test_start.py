import pytest
import os
import sys
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from handlers.start import router
from aiogram import Bot, Dispatcher
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext


@pytest.mark.asyncio
class TestStartHandler:
    """Тесты для handlers/start.py"""
    
    async def test_cmd_start(self, mock_message, mock_bot):
        """Тест команды /start"""
        from handlers.start import cmd_start
        
        # Вызываем обработчик
        await cmd_start(mock_message)
        
        # Проверяем, что ответ был отправлен
        mock_message.answer.assert_called_once()
        
        # Проверяем содержимое
        call_args = mock_message.answer.call_args
        assert "Привет! Я Санитар Дурдома" in call_args[0][0]
    
    async def test_cmd_ping(self, mock_message, mock_bot):
        """Тест команды /ping"""
        from handlers.start import cmd_ping
        
        await cmd_ping(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "Pong!" in call_args[0][0]
    
    async def test_menu_main_callback(self, mock_callback, mock_bot):
        """Тест callback главного меню"""
        from handlers.start import menu_main
        
        mock_callback.data = "menu_main"
        await menu_main(mock_callback)
        
        mock_callback.message.edit_text.assert_called_once()
    
    async def test_menu_ping_callback(self, mock_callback, mock_bot):
        """Тест callback проверки связи"""
        from handlers.start import menu_ping
        
        await menu_ping(mock_callback)
        
        mock_callback.message.answer.assert_called_once()
        call_args = mock_callback.message.answer.call_args
        assert "Pong!" in call_args[0][0]
    
    async def test_require_private_chat_private(self, mock_callback):
        """Тест проверки ЛС - приватный чат"""
        from handlers.start import require_private_chat
        
        mock_callback.message.chat.type = "private"
        result = await require_private_chat(mock_callback, "тест")
        
        assert result is True
    
    async def test_require_private_chat_group(self, mock_callback):
        """Тест проверки ЛС - групповой чат"""
        from handlers.start import require_private_chat
        
        mock_callback.message.chat.type = "group"
        result = await require_private_chat(mock_callback, "тест")
        
        assert result is False
        mock_callback.message.answer.assert_called_once()
