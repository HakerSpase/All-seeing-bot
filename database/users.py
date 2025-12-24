"""
Модуль работы с клиентами (Users).
Клиент — пользователь, который пишет владельцу.
"""

from typing import Optional, Dict
from database.supabase_client import supabase


class UsersDB:
    """Управление клиентами владельцев."""
    
    table_name = "users"
    
    @staticmethod
    def count_by_owner(owner_id: int) -> int:
        """Посчитать количество клиентов у владельца."""
        try:
            response = supabase.table(UsersDB.table_name).select("*", count="exact", head=True).eq("owner_id", owner_id).execute()
            return response.count or 0
        except Exception:
            return 0
            
    @staticmethod
    def add(user_id: int, owner_id: int, user_fullname: str, 
            username: Optional[str] = None, is_premium: bool = False) -> Optional[Dict]:
        """
        Зарегистрировать нового клиента для владельца.
        Клиент уникален в связке (user_id, owner_id).
        """
        try:
            response = supabase.table(UsersDB.table_name).upsert({
                "user_id": user_id,
                "owner_id": owner_id,
                "user_fullname": user_fullname,
                "username": username,
                "is_premium": is_premium
            }, on_conflict="user_id,owner_id").execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Ошибка добавления клиента: {e}")
            return None
    
    @staticmethod
    def get(user_id: int, owner_id: int) -> Optional[Dict]:
        """Найти клиента по ID и владельцу."""
        response = supabase.table(UsersDB.table_name).select("*").eq("user_id", user_id).eq("owner_id", owner_id).execute()
        return response.data[0] if response.data else None
    
    @staticmethod
    def update(user_id: int, owner_id: int, **kwargs) -> bool:
        """Обновить данные клиента."""
        try:
            supabase.table(UsersDB.table_name).update(kwargs).eq("user_id", user_id).eq("owner_id", owner_id).execute()
            return True
        except Exception:
            return False
