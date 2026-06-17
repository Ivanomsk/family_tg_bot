import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.logger import standard_logger, audit_logger


class TestLogger:
    """Тесты для системы логирования"""
    
    def test_standard_logger_exists(self):
        """Проверка существования стандартного логгера"""
        assert standard_logger is not None
        assert standard_logger.name == "durdom_bot"
    
    def test_audit_logger_exists(self):
        """Проверка существования audit логгера"""
        assert audit_logger is not None
        assert audit_logger.name == "audit"
    
    def test_standard_logger_level(self):
        """Проверка уровня логирования"""
        import logging
        assert standard_logger.level == logging.INFO
    
    def test_audit_logger_level(self):
        """Проверка уровня логирования"""
        import logging
        assert audit_logger.level == logging.INFO
    
    def test_standard_logger_handlers(self):
        """Проверка наличия хендлеров"""
        assert len(standard_logger.handlers) > 0
    
    def test_audit_logger_handlers(self):
        """Проверка наличия хендлеров"""
        assert len(audit_logger.handlers) > 0
    
    def test_log_directory_exists(self):
        """Проверка существования директории логов"""
        log_dir = os.path.join("bot_data", "logs")
        assert os.path.exists(log_dir)
    
    def test_log_files_exist(self):
        """Проверка существования файлов логов"""
        assert os.path.exists("bot_data/logs/bot.log")
        assert os.path.exists("bot_data/logs/audit.log")
