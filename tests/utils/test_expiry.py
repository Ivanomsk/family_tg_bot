import pytest
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.expiry import get_vpn_config_age, get_proxy_age
from config import USER_PROXIES_FILE
from database.storage import save_json, load_json


class TestExpiry:
    """Тесты для проверки сроков действия"""
    
    def test_get_vpn_config_age_expired(self):
        """Тест истёкшего VPN конфига"""
        # Создаём тестовый файл
        test_dir = "bot_data/vpn_configs/test_user"
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "test_expired.vpn")
        
        with open(test_file, "w") as f:
            f.write("test")
        
        # Мокаем os.path.getctime чтобы вернуть старую дату
        old_time = (datetime.now() - timedelta(days=31)).timestamp()
        
        with patch('os.path.getctime', return_value=old_time):
            age = get_vpn_config_age("test_user", "test_expired.vpn")
        
        assert age["status"] == "expired"
        assert age["days_left"] < 0
        
        # Cleanup
        os.remove(test_file)
    
    def test_get_vpn_config_age_active(self):
        """Тест активного VPN конфига"""
        test_dir = "bot_data/vpn_configs/test_user"
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, "active.vpn")
        
        with open(test_file, "w") as f:
            f.write("test")
        
        age = get_vpn_config_age("test_user", "active.vpn")
        
        assert age["status"] == "active"
        assert age["days_left"] > 0
        
        # Cleanup
        os.remove(test_file)
    
    def test_get_proxy_age_expired(self):
        """Тест истёкшего прокси"""
        user_proxies = load_json(USER_PROXIES_FILE, {})
        
        test_user_id = "999999999"
        user_proxies[test_user_id] = {
            "proxies": [
                {
                    "name": "expired_proxy",
                    "server": "test",
                    "port": 443,
                    "secret": "test",
                    "issued_at": (datetime.now() - timedelta(days=31)).isoformat(),
                    "issued_by": 764438696
                }
            ]
        }
        
        save_json(USER_PROXIES_FILE, user_proxies)
        
        try:
            age = get_proxy_age(int(test_user_id), "expired_proxy")
            assert age["status"] == "expired"
        finally:
            del user_proxies[test_user_id]
            save_json(USER_PROXIES_FILE, user_proxies)
    
    def test_get_proxy_age_active(self):
        """Тест активного прокси"""
        user_proxies = load_json(USER_PROXIES_FILE, {})
        
        test_user_id = "999999998"
        user_proxies[test_user_id] = {
            "proxies": [
                {
                    "name": "active_proxy",
                    "server": "test",
                    "port": 443,
                    "secret": "test",
                    "issued_at": datetime.now().isoformat(),
                    "issued_by": 764438696
                }
            ]
        }
        
        save_json(USER_PROXIES_FILE, user_proxies)
        
        try:
            age = get_proxy_age(int(test_user_id), "active_proxy")
            assert age["status"] == "active"
        finally:
            del user_proxies[test_user_id]
            save_json(USER_PROXIES_FILE, user_proxies)
    
    def test_get_proxy_age_not_found(self):
        """Тест прокси, которого нет"""
        age = get_proxy_age(999999997, "nonexistent_proxy")
        assert age["status"] == "not_found"