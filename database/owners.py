"""
Модуль работы с владельцами бота (Owners).
Владелец — пользователь, подключивший бота к Telegram Business.
"""

from typing import Optional, Dict
from database.supabase_client import supabase


class OwnersDB:
    """Управление владельцами бота."""
    
    table_name = "owners"
    
    @staticmethod
    def get_all() -> list:
        """Получить всех владельцев."""
        try:
            response = supabase.table(OwnersDB.table_name).select("*").execute()
            return response.data if response.data else []
        except Exception:
            return []

    @staticmethod
    def add(user_id: int, business_connection_id: str, user_fullname: str, 
            username: Optional[str] = None, avatar_file_id: Optional[str] = None) -> Optional[Dict]:
        """
        Зарегистрировать нового владельца.
        Использует upsert для обновления при повторном подключении.
        """
        try:
            data = {
                "user_id": user_id,
                "business_connection_id": business_connection_id,
                "user_fullname": user_fullname,
                "username": username
            }
            if avatar_file_id:
                data["avatar_file_id"] = avatar_file_id
            response = supabase.table(OwnersDB.table_name).upsert(data, on_conflict="user_id").execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Ошибка добавления владельца: {e}")
            return None
    
    @staticmethod
    def get_by_user_id(user_id: int) -> Optional[Dict]:
        """Найти владельца по Telegram ID."""
        response = supabase.table(OwnersDB.table_name).select("*").eq("user_id", user_id).execute()
        return response.data[0] if response.data else None
    
    @staticmethod
    def get_by_connection_id(business_connection_id: str) -> Optional[Dict]:
        """Найти владельца по ID бизнес-подключения."""
        response = supabase.table(OwnersDB.table_name).select("*").eq("business_connection_id", business_connection_id).execute()
        return response.data[0] if response.data else None
    
    @staticmethod
    def update_settings(user_id: int, notify_on_edit: bool) -> bool:
        """Обновить настройки владельца."""
        try:
            supabase.table(OwnersDB.table_name).update({"notify_on_edit": notify_on_edit}).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            print(f"Ошибка обновления настроек: {e}")
            return False
    
    @staticmethod
    def delete(user_id: int) -> bool:
        """Удалить владельца (при отключении бота)."""
        try:
            supabase.table(OwnersDB.table_name).delete().eq("user_id", user_id).execute()
            return True
        except Exception:
            return False
