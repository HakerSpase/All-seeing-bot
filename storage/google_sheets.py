"""
Клиент Google Sheets.
Отвечает за запись логов сообщений в Google Таблицы.
"""

import gspread
from google.oauth2.service_account import Credentials
import logging
from datetime import datetime
import json

from config import GOOGLE_KEY_FILE, GOOGLE_SPREADSHEET_ID

logger = logging.getLogger(__name__)


class GoogleLogger:
    """
    Логгер в Google Sheets.
    Открывает таблицу по ID и пишет данные пачками.
    """
    
    def __init__(self):
        """Инициализация с ключом сервисного аккаунта."""
        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        self.creds = Credentials.from_service_account_file(
            GOOGLE_KEY_FILE, scopes=self.scopes
        )
        self.client = gspread.authorize(self.creds)
        self.spreadsheet_key = GOOGLE_SPREADSHEET_ID
        self.spreadsheet = None
        self.current_sheet = None
        self.current_sheet_name = None

    def _open_spreadsheet(self):
        """Открыть таблицу по ID."""
        try:
            sheet = self.client.open_by_key(self.spreadsheet_key)
            logger.info(f"Открыта таблица: {sheet.title}")
            return sheet
        except Exception as e:
            import traceback
            logger.error(f"Ошибка открытия таблицы: {type(e).__name__}: {e}")
            logger.error(traceback.format_exc())
            raise e

    def _ensure_sheet_exists(self, date_obj: datetime):
        """
        Убедиться, что существует лист для текущего месяца.
        Формат: Log_2025_12
        """
        sheet_name = date_obj.strftime("Log_%Y_%m")
        
        # Если уже на нужном листе — выходим
        if self.current_sheet_name == sheet_name and self.current_sheet:
            return

        # Открываем таблицу, если еще не открыта
        if not self.spreadsheet:
            self.spreadsheet = self._open_spreadsheet()
            print(f"\n[Google Sheets] Логирование в: {self.spreadsheet.url}\n")

        try:
            worksheet = self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            # Создаем новый лист
            worksheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=10)
            # Добавляем заголовки
            headers = [
                "Время (UTC)", 
                "ID сообщения", 
                "ID чата (клиент)", 
                "ID владельца",
                "Направление", 
                "Тип", 
                "Содержимое", 
                "File ID", 
                "Raw JSON"
            ]
            worksheet.append_row(headers)
            # Закрепляем заголовок
            worksheet.freeze(rows=1)
            # Делаем заголовок жирным
            worksheet.format("A1:I1", {"textFormat": {"bold": True}})

        self.current_sheet = worksheet
        self.current_sheet_name = sheet_name

    def init_sheet(self):
        """Принудительная инициализация листа при старте."""
        self._ensure_sheet_exists(datetime.utcnow())

    def batch_insert(self, messages: list):
        """
        Вставить пачку сообщений в таблицу.
        Вызывается из StorageManager раз в N секунд.
        """
        if not messages:
            return

        now = datetime.utcnow()
        self._ensure_sheet_exists(now)

        rows_to_add = []
        for msg in messages:
            # Ограничиваем размер контента
            content = msg.get("message_text") or ""
            if len(content) > 5000:
                content = content[:5000] + "..."
            
            raw_json = json.dumps(msg, ensure_ascii=False)
            if len(raw_json) > 40000:
                raw_json = raw_json[:40000] + "... (обрезано)"

            extra_data = msg.get("extra_data")
            if isinstance(extra_data, str):
                 try:
                     extra_data = json.loads(extra_data)
                 except:
                     extra_data = {}
            elif not isinstance(extra_data, dict):
                extra_data = {}

            file_id = extra_data.get("file_id") or msg.get("file_id") or ""

            row = [
                msg.get("timestamp"),
                str(msg.get("message_id")),
                str(msg.get("chat_id")),
                str(msg.get("owner_id")),
                "Исходящее" if msg.get("is_outgoing") else "Входящее",
                msg.get("content_type"),
                content,
                file_id,
                raw_json
            ]
            rows_to_add.append(row)

        try:
            self.current_sheet.append_rows(rows_to_add)
            logger.info(f"Записано {len(rows_to_add)} строк в Google Sheets.")
        except Exception as e:
            logger.error(f"Ошибка записи в Google Sheets: {e}")
            raise e
