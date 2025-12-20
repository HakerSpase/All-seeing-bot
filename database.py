"""
Database module for Supabase operations.
Supports multi-owner architecture for Telegram Business bot.
"""

import configparser
from datetime import datetime
from typing import Optional, Dict, Any, List
# Import only necessary low-level clients to bypass main Client validation logic
from postgrest import SyncPostgrestClient

config = configparser.ConfigParser()
config.read("config.ini")

# Clean config values
SUPABASE_URL = config["supabase"]["url"].replace('"', '').replace("'", '').strip()
SUPABASE_KEY = config["supabase"]["key"].replace('"', '').replace("'", '').strip()

# Simple wrapper that behaves like supabase.table(...)
class SimpleSupabaseClient:
    def __init__(self, url: str, key: str):
        self.url = url
        self.key = key
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        # Direct connection to PostgREST
        self.rest_client = SyncPostgrestClient(f"{url}/rest/v1", headers=headers)

    def table(self, table_name: str):
        return self.rest_client.from_(table_name)

# Initialize our simple client
try:
    supabase = SimpleSupabaseClient(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"CRITICAL ERROR connecting to Supabase: {e}")
    raise e


class OwnersDB:
    """Manages bot owners (users who connected bot to Telegram Business)."""
    
    table_name = "owners"
    
    @staticmethod
    def update_settings(user_id: int, notify_on_edit: bool) -> bool:
        """Update owner settings."""
        try:
            supabase.table(OwnersDB.table_name).update({"notify_on_edit": notify_on_edit}).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            print(f"Error updating settings: {e}")
            return False

    @staticmethod
    def add(user_id: int, business_connection_id: str, user_fullname: str, username: Optional[str] = None) -> Optional[Dict]:
        """Register a new owner."""
        try:
            response = supabase.table(OwnersDB.table_name).upsert({
                "user_id": user_id,
                "business_connection_id": business_connection_id,
                "user_fullname": user_fullname,
                "username": username
            }, on_conflict="user_id").execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error adding owner: {e}")
            return None
    
    @staticmethod
    def get_by_user_id(user_id: int) -> Optional[Dict]:
        """Get owner by user_id."""
        response = supabase.table(OwnersDB.table_name).select("*").eq("user_id", user_id).execute()
        return response.data[0] if response.data else None
    
    @staticmethod
    def get_by_connection_id(business_connection_id: str) -> Optional[Dict]:
        """Get owner by business_connection_id."""
        response = supabase.table(OwnersDB.table_name).select("*").eq("business_connection_id", business_connection_id).execute()
        return response.data[0] if response.data else None
    
    @staticmethod
    def delete(user_id: int) -> bool:
        """Remove owner (when they disconnect the bot)."""
        try:
            supabase.table(OwnersDB.table_name).delete().eq("user_id", user_id).execute()
            return True
        except Exception:
            return False


class UsersDB:
    """Manages clients (users who message the owners)."""
    
    table_name = "users"
    
    @staticmethod
    def add(user_id: int, owner_id: int, user_fullname: str, username: Optional[str] = None) -> Optional[Dict]:
        """Register a new client for an owner."""
        try:
            response = supabase.table(UsersDB.table_name).upsert({
                "user_id": user_id,
                "owner_id": owner_id,
                "user_fullname": user_fullname,
                "username": username
            }, on_conflict="user_id,owner_id").execute()
            return response.data[0] if response.data else None
        except Exception as e:
            print(f"Error adding user: {e}")
            return None
    
    @staticmethod
    def get(user_id: int, owner_id: int) -> Optional[Dict]:
        """Get client by user_id and owner_id."""
        response = supabase.table(UsersDB.table_name).select("*").eq("user_id", user_id).eq("owner_id", owner_id).execute()
        return response.data[0] if response.data else None
    
    @staticmethod
    def update(user_id: int, owner_id: int, **kwargs) -> bool:
        """Update user fields."""
        try:
            supabase.table(UsersDB.table_name).update(kwargs).eq("user_id", user_id).eq("owner_id", owner_id).execute()
            return True
        except Exception:
            return False


class MessagesDB:
    """Manages message history with media support."""
    
    table_name = "messages"
    
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
        """Add a new message record."""
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
            print(f"Error adding message: {e}")
            return None
    
    @staticmethod
    def get(owner_id: int, chat_id: int, message_id: int) -> Optional[Dict]:
        """Get a specific message."""
        response = supabase.table(MessagesDB.table_name).select("*").eq("owner_id", owner_id).eq("chat_id", chat_id).eq("message_id", message_id).execute()
        return response.data[0] if response.data else None
    
    @staticmethod
    def get_by_chat(owner_id: int, chat_id: int, limit: int = 100) -> List[Dict]:
        """Get all messages for a specific chat."""
        response = supabase.table(MessagesDB.table_name).select("*").eq("owner_id", owner_id).eq("chat_id", chat_id).order("timestamp", desc=True).limit(limit).execute()
        return response.data if response.data else []
    
    @staticmethod
    def update(owner_id: int, chat_id: int, message_id: int, **kwargs) -> bool:
        """Update message fields."""
        try:
            supabase.table(MessagesDB.table_name).update(kwargs).eq("owner_id", owner_id).eq("chat_id", chat_id).eq("message_id", message_id).execute()
            return True
        except Exception:
            return False
    
    @staticmethod
    def delete(owner_id: int, chat_id: int, message_id: int) -> bool:
        """Delete a specific message."""
        try:
            supabase.table(MessagesDB.table_name).delete().eq("owner_id", owner_id).eq("chat_id", chat_id).eq("message_id", message_id).execute()
            return True
        except Exception:
            return False
    
    @staticmethod
    def delete_old_messages(cutoff_timestamp: str) -> int:
        """Delete messages older than cutoff. Returns count of deleted."""
        try:
            response = supabase.table(MessagesDB.table_name).delete().lt("timestamp", cutoff_timestamp).execute()
            return len(response.data) if response.data else 0
        except Exception:
            return 0
