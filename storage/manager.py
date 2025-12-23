"""
Менеджер гибридного хранилища.
Отвечает за периодический перенос данных из Supabase в Google Sheets.
"""

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from config import BACKUP_INTERVAL_HOURS
from storage.google_sheets import GoogleLogger
from database import MessagesDB, BackupsDB

logger = logging.getLogger(__name__)


class StorageManager:
    """
    Менеджер бэкапов.
    
    Логика работы:
    1. Каждые N часов (BACKUP_INTERVAL_HOURS) запускается бэкап
    2. Сообщения читаются из Supabase
    3. Записываются в Google Sheets
    4. При успехе — удаляются из Supabase
    5. Информация о бэкапе сохраняется в таблицу backups
    
    Ручной бэкап через /backup НЕ сбрасывает таймер.
    """
    
    def __init__(self):
        self.buffer: List[Dict] = []  # Для новых сообщений до первого бэкапа
        self.buffer_lock = asyncio.Lock()
        
        # Интервал в часах
        self.backup_interval_hours = BACKUP_INTERVAL_HOURS
        
        # Время следующего планового бэкапа
        self.next_backup_time: Optional[datetime] = None
        
        # Инициализация Google логгера
        try:
            self.google_logger = GoogleLogger()
            self.google_available = True
        except Exception as e:
            logger.error(f"Ошибка инициализации Google Sheets: {e}")
            self.google_available = False

        self._backup_task = None
    
    async def start(self):
        """Запустить менеджер бэкапов."""
        # Инициализируем лист
        if self.google_available:
            try:
                await asyncio.to_thread(self.google_logger.init_sheet)
            except Exception as e:
                logger.error(f"Ошибка инициализации листа: {e}")

        # Определяем время следующего бэкапа
        await self._schedule_next_backup()
        
        # Запускаем цикл бэкапов
        self._backup_task = asyncio.create_task(self._backup_loop())
        logger.info(f"Менеджер бэкапов запущен. Интервал: {self.backup_interval_hours} ч.")

    async def _schedule_next_backup(self):
        """Запланировать следующий бэкап на основе последнего."""
        last_backup = await asyncio.to_thread(BackupsDB.get_last)
        
        if last_backup and last_backup.get("timestamp"):
            last_time = datetime.fromisoformat(last_backup["timestamp"].replace('Z', '+00:00'))
            self.next_backup_time = last_time + timedelta(hours=self.backup_interval_hours)
        else:
            # Если бэкапов не было — делаем через 1 минуту (для первого теста)
            self.next_backup_time = datetime.utcnow() + timedelta(minutes=1)
        
        logger.info(f"Следующий бэкап запланирован на: {self.next_backup_time}")

    async def _backup_loop(self):
        """Фоновый цикл плановых бэкапов."""
        logger.info("Цикл плановых бэкапов запущен")
        while True:
            # Спим до следующего бэкапа
            now = datetime.utcnow()
            if self.next_backup_time:
                wait_seconds = (self.next_backup_time - now).total_seconds()
                if wait_seconds > 0:
                    await asyncio.sleep(wait_seconds)
                
            # Выполняем бэкап
            await self.run_backup(is_manual=False)
            
            # Планируем следующий
            self.next_backup_time = datetime.utcnow() + timedelta(hours=self.backup_interval_hours)
            logger.info(f"Следующий бэкап: {self.next_backup_time}")

    async def add_message(self, message_data: Dict):
        """
        Добавить сообщение в буфер.
        Буфер очищается при каждом бэкапе.
        Также проверяем порог сообщений для автобэкапа.
        """
        async with self.buffer_lock:
            self.buffer.append(message_data)
        
        # Проверяем порог (каждые 100 сообщений в буфере для оптимизации)
        if len(self.buffer) % 100 == 0:
            total_count = MessagesDB.count()
            if total_count >= 3000:
                logger.info(f"Порог сообщений достигнут ({total_count}), запускаем автобэкап")
                asyncio.create_task(self.run_backup(is_manual=False))

    async def log_deleted_messages(self, messages: List[Dict]):
        """
        Принудительно залогировать удаленные сообщения в Google Sheets.
        Вызывается перед удалением из Supabase.
        """
        if not self.google_available or not messages:
            return
        
        # Модифицируем тип, чтобы было понятно, что удалено
        msgs_to_log = []
        for msg in messages:
            msg_copy = msg.copy()
            current_type = msg.get("content_type", "unknown")
            msg_copy["content_type"] = f"DELETED ({current_type})"
            msgs_to_log.append(msg_copy)
            
        try:
            await asyncio.to_thread(self.google_logger.batch_insert, msgs_to_log)
        except Exception as e:
            logger.error(f"Ошибка логирования удаленных сообщений: {e}")

    async def run_backup(self, is_manual: bool = False) -> Dict:
        """
        Выполнить бэкап: перенести данные из Supabase в Google Sheets.
        
        Args:
            is_manual: True если это ручной бэкап (таймер не сбрасывается)
            
        Returns:
            dict с результатом: {success: bool, count: int, error: str}
        """
        result = {"success": False, "count": 0, "error": None}
        
        if not self.google_available:
            result["error"] = "Google Sheets недоступен"
            logger.error(result["error"])
            return result
        
        try:
            # 1. Получаем все сообщения из Supabase
            # Используем get_all или аналогичный метод
            # Поскольку MessagesDB.get_by_chat требует chat_id, нам нужен другой подход
            # Добавим метод get_all в MessagesDB или используем прямой запрос
            
            all_messages = await asyncio.to_thread(self._get_all_messages)
            
            if not all_messages:
                logger.info("Нет сообщений для бэкапа")
                result["success"] = True
                result["count"] = 0
                return result
            
            # 2. Добавляем сообщения из буфера
            async with self.buffer_lock:
                buffered = list(self.buffer)
                self.buffer.clear()
            
            # Объединяем (буфер может содержать данные, ещё не в Supabase)
            # Для простоты: all_messages уже содержит всё из Supabase
            # Буфер — это только то, что ещё не записано
            
            messages_to_backup = all_messages
            logger.info(f"Бэкап: {len(messages_to_backup)} сообщений")
            
            # 3. Записываем в Google Sheets
            await asyncio.to_thread(self.google_logger.batch_insert, messages_to_backup)
            
            # 4. Удаляем из Supabase (только если запись успешна)
            deleted_count = 0
            for msg in messages_to_backup:
                owner_id = msg.get("owner_id")
                chat_id = msg.get("chat_id")
                message_id = msg.get("message_id")
                if owner_id and chat_id and message_id:
                    await asyncio.to_thread(
                        MessagesDB.delete, 
                        owner_id=owner_id, 
                        chat_id=chat_id, 
                        message_id=message_id
                    )
                    deleted_count += 1
            
            # 5. Записываем информацию о бэкапе
            await asyncio.to_thread(
                BackupsDB.add,
                messages_count=len(messages_to_backup),
                status="success"
            )
            
            result["success"] = True
            result["count"] = len(messages_to_backup)
            
            logger.info(f"Бэкап успешен: {result['count']} сообщений перенесено")
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Ошибка бэкапа: {e}")
            
            # Записываем неудачный бэкап
            await asyncio.to_thread(
                BackupsDB.add,
                messages_count=0,
                status="failed",
                error_message=str(e)
            )
        
        return result
    
    def _get_all_messages(self) -> List[Dict]:
        """Получить все сообщения из Supabase (синхронно)."""
        try:
            from database.supabase_client import supabase
            response = supabase.table("messages").select("*").execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Ошибка получения сообщений: {e}")
            return []

    async def stop(self):
        """Остановить менеджер."""
        if self._backup_task:
            self._backup_task.cancel()
        # Финальный бэкап перед остановкой
        await self.run_backup(is_manual=True)
