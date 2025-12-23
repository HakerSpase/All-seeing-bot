"""
Модуль работы с бэкапами (Backups).
Хранит историю переносов данных в Google Sheets.
"""

from typing import Optional, Dict, List
from datetime import datetime
from database.supabase_client import supabase


class BackupsDB:
    """Управление историей бэкапов."""
    
    table_name = "backups"
    
    @staticmethod
    def add(
        messages_count: int,
        status: str = "success",
        error_message: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Записать информацию о бэкапе.
        
        Args:
            messages_count: Количество перенесённых сообщений
            status: Статус ('success', 'failed', 'partial')
            error_message: Сообщение об ошибке (если есть)
        """
        try:
            data = {
                "messages_count": messages_count,
                "status": status,
                "error_message": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
            response = supabase.table(BackupsDB.table_name).insert(data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Ошибка записи бэкапа: {e}")
            return None
    
    @staticmethod
    def get_last() -> Optional[Dict]:
        """Получить последний успешный бэкап."""
        try:
            response = supabase.table(BackupsDB.table_name).select("*").eq("status", "success").order("timestamp", desc=True).limit(1).execute()
            return response.data[0] if response.data else None
        except Exception:
            return None
    
    @staticmethod
    def get_all(limit: int = 50) -> List[Dict]:
        """Получить историю бэкапов."""
        try:
            response = supabase.table(BackupsDB.table_name).select("*").order("timestamp", desc=True).limit(limit).execute()
            return response.data if response.data else []
        except Exception:
            return []
    
    @staticmethod
    def get_stats() -> Dict:
        """Получить статистику бэкапов."""
        try:
            all_backups = BackupsDB.get_all(100)
            success_count = sum(1 for b in all_backups if b.get("status") == "success")
            total_messages = sum(b.get("messages_count", 0) for b in all_backups if b.get("status") == "success")
            last_backup = BackupsDB.get_last()
            
            return {
                "total_backups": len(all_backups),
                "success_backups": success_count,
                "total_messages_transferred": total_messages,
                "last_backup_time": last_backup.get("timestamp") if last_backup else None
            }
        except Exception:
            return {}
