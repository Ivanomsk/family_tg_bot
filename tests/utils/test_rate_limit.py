import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.rate_limit import is_rate_limited


class TestRateLimit:
    """Тесты для rate limiting"""
    
    def test_first_request_allowed(self):
        """Первый запрос всегда разрешён"""
        # Используем уникальный ID и действие
        is_limited, retry_after = is_rate_limited(111111111, "test_action_unique_1")
        assert is_limited is False
        assert retry_after == 0
    
    def test_second_request_allowed(self):
        """Второй запрос в пределах лимита разрешён"""
        is_limited1, _ = is_rate_limited(222222222, "test_action_unique_2")
        is_limited2, _ = is_rate_limited(222222222, "test_action_unique_2")
        assert is_limited1 is False
        assert is_limited2 is False
    
    def test_different_users_independent(self):
        """Разные пользователи не влияют друг на друга"""
        is_limited1, _ = is_rate_limited(333333333, "test_action_unique_3")
        is_limited2, _ = is_rate_limited(444444444, "test_action_unique_3")
        
        assert is_limited1 is False
        assert is_limited2 is False
    
    def test_different_actions_independent(self):
        """Разные действия не влияют друг на друга"""
        is_limited1, _ = is_rate_limited(555555555, "test_action_A")
        is_limited2, _ = is_rate_limited(555555555, "test_action_B")
        
        assert is_limited1 is False
        assert is_limited2 is False