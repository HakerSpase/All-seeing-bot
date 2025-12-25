"""
All-Seeing Bot - Telegram Business Message Tracker
Главный файл запуска бота.

Отслеживает редактирование и удаление сообщений в бизнес-чатах.
"""

import asyncio
import logging
import json
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, types
from aiohttp import web, ClientTimeout
import os
import hashlib

from config import TOKEN, TIMEZONE, ADMIN_ID
from storage import StorageManager
from handlers import commands_router, business_router, set_storage_manager
from database import MessagesDB
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


async def handle_logs(request):
    """API endpoint для получения логов из Google Sheets (через локальный Proxy)."""
    storage_mgr = request.app['storage_mgr']
    
    owner_id = request.query.get('owner_id')
    chat_id = request.query.get('chat_id')
    
    if not owner_id or not chat_id:
        return web.json_response({'error': 'Missing params'}, status=400)
    
    try:
        # ГИБРИДНЫЙ РЕЖИМ: Supabase + Google Sheets
        logger.info(f"API: Fetch logs request for {owner_id} -> {chat_id}")
        
        # 1. Supabase (Быстро, новые фичи, статус удаления)
        db_task = asyncio.to_thread(MessagesDB.get_by_chat, int(owner_id), int(chat_id), limit=1000)
        
        # 2. Google Sheets (Медленно, архив, старая история)
        # Если нужно ускорить, можно вызывать только если offset большой, но пока грузим всё
        gs_task = asyncio.to_thread(storage_mgr.google_logger.fetch_logs, int(owner_id), int(chat_id))
        
        # Запускаем параллельно
        results = await asyncio.gather(db_task, gs_task, return_exceptions=True)
        
        db_logs = results[0] if isinstance(results[0], list) else []
        gs_logs = results[1] if isinstance(results[1], list) else []
        
        if isinstance(results[1], Exception):
             logger.error(f"Google Sheets Fetch Error: {results[1]}")
             
        # 3. Объединение и дедупликация
        # Приоритет у Supabase (так как там свежие статусы is_deleted, edit_history)
        
        merged_map = {}
        
        # Сначала кладем Google Sheets (как "базу")
        for msg in gs_logs:
            mid = str(msg.get("message_id"))
            merged_map[mid] = msg
            
        # Потом накладываем Supabase (перезаписываем, т.к. там актуальнее)
        for msg in db_logs:
            mid = str(msg.get("message_id"))
            # Если сообщение уже есть, обновляем поля, которые могли измениться
            # Но проще просто перезаписать объект целиком, так как Supabase - source of truth для состояния
            merged_map[mid] = msg
            
        # Превращаем обратно в список
        all_logs = list(merged_map.values())
        
        # 4. Сортировка (новые сверху/снизу? ChatView ждет, обычно сортируем по timestamp DESC)
        # timestamp iso string sortable
        all_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Лимит на всякий случай
        final_logs = all_logs[:1000]
        
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
        return web.json_response(final_logs, headers=headers)
        
    except Exception as e:
        logger.error(f"API Error: {e}")
        return web.json_response({'error': str(e)}, status=500, headers={"Access-Control-Allow-Origin": "*"})

CACHE_DIR = "media_cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR, exist_ok=True)

async def handle_file(request):
    """
    Проксирование файла Telegram с локальным кешированием.
    1. Проверяем кеш (по хешу file_id).
    2. Если нет в кеше - скачиваем с Telegram (с ретраями).
    3. Сохраняем в кеш и отдаем.
    """
    bot = request.app['bot']
    file_id = request.query.get('file_id')
    filename_param = request.query.get('filename') # Опциональное имя файла для скачивания
    
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
        "Cache-Control": "public, max-age=31536000" # Кешировать на год в браузере
    }

    if filename_param:
        # Добавляем Content-Disposition attachment для скачивания с именем
        headers["Content-Disposition"] = f'attachment; filename="{filename_param}"'

    if not file_id:
        return web.Response(status=400, text="Missing file_id", headers=headers)

    # 1. Проверяем кеш
    # Используем MD5 от file_id как имя файла, чтобы избежать проблем с длиной пути и спецсимволами
    file_hash = hashlib.md5(file_id.encode()).hexdigest()
    # Определяем расширение нельзя точно, но можно попробовать угадать или сохранить без него
    # Для простоты сохраняем как есть, Content-Type браузер сам поймет или мы сохраним его?
    # Лучше сохранять без расширения, контент проксируем.
    
    local_path = os.path.join(CACHE_DIR, file_hash)
    
    if os.path.exists(local_path):
        # Отдаем из кеша
        # logger.info(f"Cache HIT: {file_id[:10]}...")
        return web.FileResponse(local_path, headers=headers)
        
    # 2. Скачиваем
    logger.info(f"Cache MISS: Downloading {file_id[:10]}...")
    
    try:
        # Получаем путь файла (это тоже делает запрос к API)
        # Добавим простой ретрай на получение пути
        file_path = None
        for i in range(3):
            try:
                file = await bot.get_file(file_id)
                file_path = file.file_path
                break
            except Exception as e:
                if i == 2: raise e
                await asyncio.sleep(0.5)
        
        if not file_path:
            raise Exception("Could not get file path")

        download_url = f"https://api.telegram.org/file/bot{TOKEN}/{file_path}"
        
        session = request.app['http_session']
        
        # Скачиваем файл
        timeout = ClientTimeout(total=30, connect=10) # Таймаут 30 сек
        async with session.get(download_url, timeout=timeout) as resp:
            if resp.status != 200:
                logger.error(f"TG Download Error: {resp.status}")
                return web.Response(status=resp.status, headers=headers)
            
            # Читаем весь файл в память (для картинок ок, для видео лучше стримить в файл)
            content = await resp.read()
            
            # Сохраняем в кеш
            # Используем временный файл чтобы избежать частичной записи
            temp_path = local_path + ".tmp"
            with open(temp_path, "wb") as f:
                f.write(content)
            
            # Атомарное перемещение
            os.replace(temp_path, local_path)
            
            # Отдаем клиенту
            return web.Response(body=content, headers={
                "Content-Type": resp.headers.get("Content-Type", "application/octet-stream"),
                **headers
            })

    except Exception as e:
        logger.error(f"Proxy Error: {e}")
        return web.json_response({'error': str(e)}, status=500, headers=headers)

async def handle_options(request):
    """CORS preflight."""
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }
    return web.Response(headers=headers)


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
    
    # Запуск API сервера (локальный прокси для фронтенда)
    import aiohttp
    app = web.Application()
    app['storage_mgr'] = storage_mgr
    app['bot'] = bot
    app['http_session'] = aiohttp.ClientSession()
    
    app.add_routes([
        web.get('/api/logs', handle_logs),
        web.options('/api/logs', handle_options),
        web.get('/api/file', handle_file),
        web.options('/api/file', handle_options),
    ])
    
    runner = web.AppRunner(app)
    await runner.setup()
    # Слушаем на 0.0.0.0, чтобы было доступно снаружи (не только localhost)
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Local API Server started at http://0.0.0.0:8080")
    
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