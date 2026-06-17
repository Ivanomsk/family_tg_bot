import pytest
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.notifications import send_proxy_expiry_notification


class TestNotifications:
    """Тесты для уведомлений"""
    
    @pytest.mark.asyncio
    async def test_send_proxy_expiry_notification_no_expired(self):
        """Тест уведомления без истёкших прокси"""
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()
        
        expired = []
        expiring = [{"name": "test_proxy", "days_left": 5}]
        
        # Мокаем can_notify чтобы всегда возвращал True
        with patch('utils.notifications.can_notify', return_value=True):
            with patch('utils.notifications.ALLOWED_CHAT_ID', -100123456789):
                await send_proxy_expiry_notification(
                    mock_bot, 123456, "test_user", expired, expiring
                )
        
        # Проверяем, что сообщение было отправлено
        mock_bot.send_message.assert_called_once()
        
        # Проверяем содержимое
        call_args = mock_bot.send_message.call_args
        assert "test_proxy" in call_args[0][1] or "5" in str(call_args[0][1])
    
    @pytest.mark.asyncio
    async def test_send_proxy_expiry_notification_with_expired(self):
        """Тест уведомления с истёкшими прокси"""
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()
        
        expired = [{"name": "expired_proxy", "days_expired": 10}]
        expiring = []
        
        with patch('utils.notifications.can_notify', return_value=True):
            with patch('utils.notifications.ALLOWED_CHAT_ID', -100123456789):
                await send_proxy_expiry_notification(
                    mock_bot, 123456, "test_user", expired, expiring
                )
        
        mock_bot.send_message.assert_called_once()
        
        call_args = mock_bot.send_message.call_args
        assert "expired_proxy" in call_args[0][1] or "10" in str(call_args[0][1])
    
    @pytest.mark.asyncio
    async def test_send_proxy_expiry_notification_both(self):
        """Тест уведомления с истёкшими и истекающими прокси"""
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()
        
        expired = [{"name": "expired1", "days_expired": 5}]
        expiring = [{"name": "expiring1", "days_left": 3}]
        
        with patch('utils.notifications.can_notify', return_value=True):
            with patch('utils.notifications.ALLOWED_CHAT_ID', -100123456789):
                await send_proxy_expiry_notification(
                    mock_bot, 123456, "test_user", expired, expiring
                )
        
        # Должно быть вызвано один раз
        mock_bot.send_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_proxy_expiry_notification_empty(self):
        """Тест уведомления без прокси"""
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()
        
        expired = []
        expiring = []
        
        with patch('utils.notifications.can_notify', return_value=True):
            with patch('utils.notifications.ALLOWED_CHAT_ID', -100123456789):
                await send_proxy_expiry_notification(
                    mock_bot, 123456, "test_user", expired, expiring
                )
        
        # Не должно вызываться, если нет истёкших/истекающих
        mock_bot.send_message.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_send_proxy_expiry_notification_cooldown(self):
        """Тест cooldown системы"""
        mock_bot = AsyncMock()
        mock_bot.send_message = AsyncMock()
        
        expired = [{"name": "test_proxy", "days_expired": 5}]
        expiring = []
        
        # Мокаем can_notify чтобы возвращал False (cooldown активен)
        with patch('utils.notifications.can_notify', return_value=False):
            with patch('utils.notifications.ALLOWED_CHAT_ID', -100123456789):
                await send_proxy_expiry_notification(
                    mock_bot, 123456, "test_user", expired, expiring
                )
        
        # Не должно вызываться из-за cooldown
        mock_bot.send_message.assert_not_called()