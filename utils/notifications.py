"""
Функции отправки уведомлений.
"""

import logging
from aiogram import Bot
from aiogram.types import LinkPreviewOptions

logger = logging.getLogger(__name__)


async def send_notification(bot: Bot, owner_id: int, message: str) -> bool:
    """
    Отправить уведомление владельцу.
    Предпросмотр ссылок отключен для чистого отображения.
    
    Args:
        bot: Экземпляр бота
        owner_id: ID пользователя-получателя
        message: HTML-текст сообщения
        
    Returns:
        True если отправлено успешно, False при ошибке
    """
    try:
        await bot.send_message(
            owner_id, 
            message, 
            parse_mode='html',
            link_preview_options=LinkPreviewOptions(is_disabled=True)
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления {owner_id}: {e}")
        return False
