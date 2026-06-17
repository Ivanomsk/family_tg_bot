import pytest
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from handlers.admin import router


@pytest.mark.asyncio
class TestAdminHandler:
    """Тесты для handlers/admin.py"""
    
    async def test_cmd_stats_admin(self, mock_message, mock_bot):
        """Тест команды /stats для админа"""
        from handlers.admin import cmd_stats
        
        mock_message.from_user.id = 764438696  # Админ
        mock_message.text = "/stats"
        
        with patch('handlers.admin.load_json', return_value={
            "764438696": {"username": "test", "actions": {"start": 10}}
        }):
            await cmd_stats(mock_message)
        
        mock_message.answer.assert_called_once()
    
    async def test_cmd_stats_non_admin(self, mock_message, mock_bot):
        """Тест команды /stats для не-админа"""
        from handlers.admin import cmd_stats
        
        mock_message.from_user.id = 999999999  # Не админ
        mock_message.text = "/stats"
        
        await cmd_stats(mock_message)
        
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args
        assert "только администратору" in call_args[0][0].lower() or "❌" in call_args[0][0]
    
    async def test_cmd_configs_admin(self, mock_message, mock_bot):
        """Тест команды /configs для админа"""
        from handlers.admin import cmd_configs
        
        mock_message.from_user.id = 764438696
        mock_message.text = "/configs"
        
        with patch('os.path.exists', return_value=True):
            with patch('os.listdir', return_value=['user1', 'user2']):
                with patch('os.path.isdir', return_value=True):
                    with patch('os.listdir', return_value=['test.vpn']):
                        await cmd_configs(mock_message)
        
        mock_message.answer.assert_called_once()
    
    async def test_cmd_clearproxy_admin(self, mock_message, mock_bot):
        """Тест команды /clearproxy для админа"""
        from handlers.admin import cmd_clearproxy
        
        mock_message.from_user.id = 764438696
        mock_message.text = "/clearproxy testuser"
        
        with patch('handlers.admin.load_json', return_value={"123456": {"proxies": []}}):
            with patch('handlers.admin.save_json'):
                await cmd_clearproxy(mock_message)
        
        mock_message.answer.assert_called_once()
    
    async def test_cmd_check_vpn_expiry_admin(self, mock_message, mock_bot):
        """Тест команды проверки VPN для админа"""
        from handlers.admin import cmd_check_vpn_expiry
        
        mock_message.from_user.id = 764438696
        mock_message.text = "/check_vpn"
        
        with patch('utils.expiry.check_all_vpn_expiry', return_value=([], [])):
            await cmd_check_vpn_expiry(mock_message)
        
        mock_message.answer.assert_called_once()
    
    async def test_cmd_check_proxy_expiry_admin(self, mock_message, mock_bot):
        """Тест команды проверки прокси для админа"""
        from handlers.admin import cmd_check_proxy_expiry
        
        mock_message.from_user.id = 764438696
        mock_message.text = "/check_proxy"
        
        with patch('utils.expiry.check_all_proxy_expiry', return_value=([], [])):
            await cmd_check_proxy_expiry(mock_message)
        
        mock_message.answer.assert_called_once()