"""
Модуль работы с сообщениями (Messages).
Хранит историю сообщений для отслеживания изменений и удалений.
"""

from typing import Optional, Dict, List
from database.supabase_client import supabase


class MessagesDB:
    """Управление историей сообщений."""
    
    table_name = "messages"
    
    @staticmethod
    def count() -> int:
        """Получить общее количество сообщений в базе."""
        try:
            # Используем select id и считаем длину - надёжнее чем count parameter
            response = supabase.table(MessagesDB.table_name).select("id").execute()
            return len(response.data) if response.data else 0
        except Exception as e:
            print(f"DEBUG: Error in MessagesDB.count: {e}")
            return 0
    
    @staticmethod
    def count_by_owner(owner_id: int) -> int:
        """Получить количество сообщений конкретного владельца."""
        try:
            response = supabase.table(MessagesDB.table_name).select("id").eq("owner_id", owner_id).execute()
            return len(response.data) if response.data else 0
        except Exception:
            return 0
    
    @staticmethod
    def add(
        owner_id: int,
        chat_id: int,
        message_id: int,
        timestamp: str,
        sender_id: int,
        sender_fullname: str,
        sender_username: Optional[str] = None,
        is_outgoing: bool = False,
        content_type: str = "text",
        message_text: Optional[str] = None,
        media_duration: Optional[int] = None,
        media_file_size: Optional[int] = None,
        extra_data: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Сохранить новое сообщение.
        Вызывается при каждом входящем/исходящем сообщении.
        """
        try:
            data = {
                "owner_id": owner_id,
                "chat_id": chat_id,
                "message_id": message_id,
                "sender_id": sender_id,
                "sender_fullname": sender_fullname,
                "sender_username": sender_username,
                "is_outgoing": is_outgoing,
                "content_type": content_type,
                "message_text": message_text,
                "media_duration": media_duration,
                "media_file_size": media_file_size,
                "extra_data": extra_data,
                "timestamp": timestamp
            }
            response = supabase.table(MessagesDB.table_name).insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Ошибка сохранения сообщения: {e}")
            return None
    
    @staticmethod
    def get(owner_id: int, chat_id: int, message_id: int) -> Optional[Dict]:
        """Найти конкретное сообщение по ID."""
        response = supabase.table(MessagesDB.table_name).select("*").eq("owner_id", owner_id).eq("chat_id", chat_id).eq("message_id", message_id).execute()
        return response.data[0] if response.data else None
    
    @staticmethod
    def get_by_chat(owner_id: int, chat_id: int, limit: int = 100) -> List[Dict]:
        """Получить последние сообщения из чата."""
        response = supabase.table(MessagesDB.table_name).select("*").eq("owner_id", owner_id).eq("chat_id", chat_id).order("timestamp", desc=True).limit(limit).execute()
        return response.data if response.data else []
    
    @staticmethod
    def update(owner_id: int, chat_id: int, message_id: int, **kwargs) -> bool:
        """Обновить сообщение (например, новый текст после редактирования)."""
        try:
            supabase.table(MessagesDB.table_name).update(kwargs).eq("owner_id", owner_id).eq("chat_id", chat_id).eq("message_id", message_id).execute()
            return True
        except Exception:
            return False
    
    @staticmethod
    def delete(owner_id: int, chat_id: int, message_id: int) -> bool:
        """Удалить сообщение из базы (после обработки удаления)."""
        try:
            supabase.table(MessagesDB.table_name).delete().eq("owner_id", owner_id).eq("chat_id", chat_id).eq("message_id", message_id).execute()
            return True
        except Exception:
            return False
    
    @staticmethod
    def delete_old_messages(cutoff_timestamp: str) -> int:
        """Удалить старые сообщения (очистка по расписанию)."""
        try:
            response = supabase.table(MessagesDB.table_name).delete().lt("timestamp", cutoff_timestamp).execute()
            return len(response.data) if response.data else 0
        except Exception:
            return 0
