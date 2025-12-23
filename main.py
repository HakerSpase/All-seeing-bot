"""
All-Seeing Bot - Telegram Business Message Tracker
Главный файл запуска бота.

Отслеживает редактирование и удаление сообщений в бизнес-чатах.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, types

from config import TOKEN, TIMEZONE, ADMIN_ID
from storage import StorageManager
from handlers import commands_router, business_router, set_storage_manager
from database import MessagesDB

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Действия при запуске бота."""
    from aiogram.types import BotCommandScopeChat, BotCommandScopeDefault
    
    # Команды для всех пользователей
    await bot.set_my_commands(
        commands=[
            types.BotCommand(command="start", description="Перезапуск / Статус"),
            types.BotCommand(command="settings", description="Настройки"),
        ],
        scope=BotCommandScopeDefault()
    )
    
    # Расширенное меню для админа (с /backup)
    if ADMIN_ID:
        try:
            await bot.set_my_commands(
                commands=[
                    types.BotCommand(command="start", description="Перезапуск / Статус"),
                    types.BotCommand(command="settings", description="Настройки"),
                    types.BotCommand(command="backup", description="Ручной бэкап"),
                    types.BotCommand(command="users", description="Пользователи"),
                ],
                scope=BotCommandScopeChat(chat_id=ADMIN_ID)
            )
            logger.info(f"Меню админа установлено для ID: {ADMIN_ID}")
        except Exception as e:
            logger.warning(f"Не удалось установить меню админа: {e}")


async def cleanup_old_messages():
    """
    Фоновая задача очистки старых сообщений.
    Запускается каждую полночь, удаляет сообщения старше 30 дней.
    """
    while True:
        now_local = datetime.now(TIMEZONE)
        # Следующий запуск в полночь
        next_run = now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        sleep_seconds = (next_run - now_local).total_seconds()
        await asyncio.sleep(sleep_seconds)
        
        cutoff_datetime = datetime.now(timezone.utc) - timedelta(days=30)
        cutoff_timestamp = cutoff_datetime.isoformat()
        deleted_count = MessagesDB.delete_old_messages(cutoff_timestamp)
        logger.info(f"Очистка: удалено {deleted_count} старых сообщений")


async def main() -> None:
    """Точка входа."""
    # Инициализация бота
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    
    # Подключение роутеров
    dp.include_router(commands_router)
    dp.include_router(business_router)
    
    # Регистрация startup
    dp.startup.register(on_startup)
    
    # Инициализация хранилища
    storage_mgr = StorageManager()
    await storage_mgr.start()
    set_storage_manager(storage_mgr)
    
    # Запуск фоновой очистки
    asyncio.create_task(cleanup_old_messages())
    
    logger.info("Бот запускается...")
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Бесконечный цикл перезапуска при сбоях сети
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            logger.error(f"Критическая ошибка (перезапуск через 5с): {e}")
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())