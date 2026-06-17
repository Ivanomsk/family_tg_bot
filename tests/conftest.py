import pytest
import os
import sys
from unittest.mock import AsyncMock, MagicMock
from aiogram import Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ADMIN_IDS, USER_PROXIES_FILE, VPN_DIR


@pytest.fixture
def mock_bot():
    """Мок бота"""
    bot = AsyncMock(spec=Bot)
    bot.id = 8769387543
    bot.username = "DurdomVPN26_Bot"
    return bot


@pytest.fixture
def mock_dispatcher(mock_bot):
    """Мок диспетчера"""
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    return dp


@pytest.fixture
def mock_message(mock_bot):
    """Мок сообщения"""
    message = MagicMock()
    message.bot = mock_bot
    message.chat.id = 123456789
    message.chat.type = "private"
    message.from_user.id = 764438696
    message.from_user.username = "test_user"
    message.from_user.first_name = "Test"
    message.text = "/start"
    message.message_id = 1
    message.answer = AsyncMock()
    message.answer_document = AsyncMock()
    message.delete = AsyncMock()
    return message


@pytest.fixture
def mock_callback(mock_bot):
    """Мок callback query"""
    callback = MagicMock()
    callback.bot = mock_bot
    callback.message.chat.id = 123456789
    callback.message.chat.type = "private"
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.from_user.id = 764438696
    callback.from_user.username = "test_user"
    callback.data = "menu_main"
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def mock_state():
    """Мок FSM состояния"""
    state = AsyncMock(spec=FSMContext)
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    state.get_state = AsyncMock()
    return state


@pytest.fixture
def sample_user_proxies():
    """Пример данных прокси"""
    return {
        "764438696": {
            "proxies": [
                {
                    "name": "Основной",
                    "server": "nas-msk.family-msk.ru",
                    "port": 4438,
                    "secret": "test_secret_123",
                    "issued_at": "2026-06-14T10:00:00",
                    "issued_by": 764438696
                }
            ]
        }
    }


@pytest.fixture
def sample_stats():
    """Пример статистики"""
    return {
        "764438696": {
            "username": "test_user",
            "name": "Test User",
            "actions": {
                "start": 10,
                "vpn": 5,
                "proxy": 3
            }
        }
    }
