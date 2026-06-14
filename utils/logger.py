import logging
import os
from logging.handlers import RotatingFileHandler

# Пути к логам
LOG_DIR = os.path.join("bot_data", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Форматирование
STANDARD_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
AUDIT_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_standard_logger(name: str = "durdom_bot") -> logging.Logger:
    """Стандартный логгер для обычных событий бота."""
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(STANDARD_FORMAT, datefmt=DATE_FORMAT)
    
    # Файловый хендлер с ротацией
    log_file = os.path.join(LOG_DIR, "bot.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Консольный хендлер
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


def setup_audit_logger(name: str = "audit") -> logging.Logger:
    """Отдельный audit-логгер для критических действий."""
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter(AUDIT_FORMAT, datefmt=DATE_FORMAT)
    
    # Файловый хендлер с ротацией
    log_file = os.path.join(LOG_DIR, "audit.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=2*1024*1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Консольный хендлер
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


# Глобальные экземпляры
standard_logger = setup_standard_logger()
audit_logger = setup_audit_logger()