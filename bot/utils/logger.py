import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler
from bot.config import LOG_DIR

def setup_logger(name: str = "bot") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
    
    file_handler = RotatingFileHandler(LOG_DIR / f"{name}.log", maxBytes=5_000_000, backupCount=5)
    file_handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

bot_logger = setup_logger("bot")
audit_logger = setup_logger("audit")
backup_logger = setup_logger("backup")
cron_logger = setup_logger("cron")
