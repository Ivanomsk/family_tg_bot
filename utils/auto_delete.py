import asyncio
import logging
from config import (
    ADMIN_IDS,
    DELETE_DELAY_TEMP,
    DELETE_DELAY_USER,
    DELETE_DELAY_PROXY_CARD,
    DELETE_DELAY_ADMIN,
    DELETE_DELAY_NEVER
)

logger = logging.getLogger(__name__)

def schedule_delete(bot, chat_id, message_id, delay=None, user_id=None, chat_type="private", allow_group=False):
    """
    Гибкое удаление сообщений с разными таймерами.
    
    Args:
        bot: объект бота
        chat_id: ID чата
        message_id: ID сообщения
        delay: задержка в секундах
        user_id: ID пользователя
        chat_type: тип чата
        allow_group: разрешить удаление в групповых чатах (для сообщений об ошибках)
    """
    # Групповые чаты — не удаляем, ЕСЛИ явно не разрешено
    if chat_type != "private" and not allow_group:
        return
    
    # Если delay не указан — определяем автоматически
    if delay is None:
        if user_id and user_id in ADMIN_IDS:
            delay = DELETE_DELAY_ADMIN
        else:
            delay = DELETE_DELAY_USER
    
    # Если delay=0 — не удаляем
    if delay == DELETE_DELAY_NEVER or delay == 0:
        return
    
    async def _delete():
        await asyncio.sleep(delay)
        try:
            await bot.delete_message(chat_id, message_id)
            logger.debug(f"Удалено сообщение {message_id} в чате {chat_id} через {delay} сек")
        except Exception as e:
            logger.debug(f"Не удалось удалить сообщение {message_id}: {e}")
    
    asyncio.create_task(_delete())


# ============================================
# УДОБНЫЕ ФУНКЦИИ-ПОМОЩНИКИ
# ============================================

def delete_temp(bot, chat_id, message_id, user_id=None, chat_type="private", allow_group=False):
    """Удалить временное уведомление через DELETE_DELAY_TEMP сек"""
    schedule_delete(bot, chat_id, message_id, delay=DELETE_DELAY_TEMP, user_id=user_id, chat_type=chat_type, allow_group=allow_group)

def delete_user(bot, chat_id, message_id, user_id=None, chat_type="private"):
    """Удалить обычное сообщение пользователя"""
    schedule_delete(bot, chat_id, message_id, delay=None, user_id=user_id, chat_type=chat_type)

def delete_proxy_card(bot, chat_id, message_id, user_id=None, chat_type="private"):
    """Удалить карточку прокси через DELETE_DELAY_PROXY_CARD сек"""
    schedule_delete(bot, chat_id, message_id, delay=DELETE_DELAY_PROXY_CARD, user_id=user_id, chat_type=chat_type)

def delete_admin(bot, chat_id, message_id, user_id=None, chat_type="private"):
    """Удалить сообщение админа через DELETE_DELAY_ADMIN сек"""
    schedule_delete(bot, chat_id, message_id, delay=DELETE_DELAY_ADMIN, user_id=user_id, chat_type=chat_type)

def delete_never(bot, chat_id, message_id, user_id=None, chat_type="private"):
    """Никогда не удалять"""
    schedule_delete(bot, chat_id, message_id, delay=DELETE_DELAY_NEVER, user_id=user_id, chat_type=chat_type)