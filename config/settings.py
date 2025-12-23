"""
Модуль конфигурации.
Загружает настройки из переменных окружения (.env) и config.ini.
Все секретные ключи хранятся в .env файле (добавлен в .gitignore).
"""

import os
import configparser
import pytz
import importlib
from pathlib import Path
from dotenv import load_dotenv

# Определяем корневую папку проекта
ROOT_DIR = Path(__file__).parent.parent

# Загружаем переменные окружения из .env
load_dotenv(ROOT_DIR / ".env")

# Загружаем конфигурацию из config.ini (не-секретные настройки)
config = configparser.ConfigParser()
config.read(ROOT_DIR / "config.ini")

# === СЕКРЕТЫ (из .env) ===
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env файле!")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL и SUPABASE_KEY должны быть в .env файле!")

GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "")

# === НАСТРОЙКИ БЭКАПОВ ===
BACKUP_INTERVAL_HOURS = int(os.getenv("BACKUP_INTERVAL_HOURS", "24"))
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# === НАСТРОЙКИ (из config.ini) ===
TIMEZONE_NAME = config.get("timezone", "name", fallback="Europe/Moscow").strip('"')
TIMEZONE = pytz.timezone(TIMEZONE_NAME)

LANGUAGE = config.get("settings", "language", fallback="ru").strip('"')

# === ПУТИ ===
GOOGLE_KEY_FILE = str(ROOT_DIR / "google_key.json")

# Загружаем языковой модуль
try:
    lang = importlib.import_module(f"config.languages.{LANGUAGE}")
except ImportError:
    raise ImportError(f"Языковой модуль '{LANGUAGE}' не найден в config/languages/")
