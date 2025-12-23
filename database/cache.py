"""
Локальный кеш сообщений в памяти.
Обеспечивает мгновенный доступ к сообщениям, пока Supabase сохраняет их асинхронно.
"""

import threading
from typing import Dict, Optional
from collections import OrderedDict


class MessageCache:
    """
    Потокобезопасный LRU-кеш для сообщений.
    Ключ: (owner_id, chat_id, message_id)
    Значение: dict с данными сообщения
    """
    
    def __init__(self, max_size: int = 10000):
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
    
    def _make_key(self, owner_id: int, chat_id: int, message_id: int) -> tuple:
        return (owner_id, chat_id, message_id)
    
    def set(self, owner_id: int, chat_id: int, message_id: int, data: Dict):
        """Сохранить сообщение в кеш."""
        key = self._make_key(owner_id, chat_id, message_id)
        with self._lock:
            # Удаляем старый ключ если есть (для LRU)
            if key in self._cache:
                del self._cache[key]
            self._cache[key] = data
            # Ограничиваем размер
            while len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
    
    def get(self, owner_id: int, chat_id: int, message_id: int) -> Optional[Dict]:
        """Получить сообщение из кеша."""
        key = self._make_key(owner_id, chat_id, message_id)
        with self._lock:
            if key in self._cache:
                # Перемещаем в конец (LRU)
                self._cache.move_to_end(key)
                return self._cache[key].copy()
            return None
    
    def update(self, owner_id: int, chat_id: int, message_id: int, **kwargs):
        """Обновить данные сообщения в кеше."""
        key = self._make_key(owner_id, chat_id, message_id)
        with self._lock:
            if key in self._cache:
                self._cache[key].update(kwargs)
                self._cache.move_to_end(key)
    
    def delete(self, owner_id: int, chat_id: int, message_id: int):
        """Удалить сообщение из кеша."""
        key = self._make_key(owner_id, chat_id, message_id)
        with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    def size(self) -> int:
        """Текущий размер кеша."""
        with self._lock:
            return len(self._cache)


# Глобальный экземпляр кеша
message_cache = MessageCache()
