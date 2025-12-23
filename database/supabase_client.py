"""
Клиент Supabase.
Инициализирует подключение к базе данных.
"""

from postgrest import SyncPostgrestClient
from config import SUPABASE_URL, SUPABASE_KEY


class SimpleSupabaseClient:
    """
    Простой клиент для работы с Supabase через PostgREST.
    Обходит проблемы с pydantic-совместимостью официального клиента.
    """
    
    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        # Прямое подключение к PostgREST API
        self.rest_client = SyncPostgrestClient(f"{url}/rest/v1", headers=headers)

    def table(self, table_name: str):
        """Получить доступ к таблице для запросов."""
        return self.rest_client.from_(table_name)


# Инициализируем глобальный клиент
try:
    supabase = SimpleSupabaseClient(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"КРИТИЧЕСКАЯ ОШИБКА подключения к Supabase: {e}")
    raise e
