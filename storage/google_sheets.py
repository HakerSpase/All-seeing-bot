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
            parsed_extra = {}
            
            if isinstance(extra_data, dict):
                parsed_extra = extra_data
            elif isinstance(extra_data, str):
                try:
                    loaded = json.loads(extra_data)
                    # Если дважды закодировано (вернулась строка), пробуем еще раз
                    if isinstance(loaded, str):
                        try:
                            loaded = json.loads(loaded)
                        except:
                            pass
                    
                    if isinstance(loaded, dict):
                        parsed_extra = loaded
                except:
                    pass

            file_id = parsed_extra.get("file_id") or msg.get("file_id") or ""
            
            # Если текст пустой, пробуем взять описание из метаданных (имя файла, трек, гео)
            if not content:
                content = parsed_extra.get("info") or parsed_extra.get("file_name") or parsed_extra.get("caption") or ""
                
            # Если это документ/фото без подписи, но есть file_id, можно написать тип
            if not content and file_id:
                type_name = msg.get("content_type", "")
                if type_name:
                    content = f"[{type_name}]"

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

    def fetch_logs(self, owner_id: int, chat_id: int) -> list:
        """
        Получить логи переписки из Google Sheets.
        Сканирует листы за последние 1.5 года ПАРАЛЛЕЛЬНО.
        """
        if not self.spreadsheet:
            try:
                self.spreadsheet = self._open_spreadsheet()
            except:
                return []

        all_messages = []
        
        # Генерируем список листов
        to_check = ['Sheet1']
        start_year = 2024
        now = datetime.utcnow()
        current_year = now.year
        current_month = now.month - 1 
        
        for year in range(start_year, current_year + 2):
            for month in range(12):
                if year > current_year: break
                if year == current_year and month > current_month: break
                to_check.append(f"Log_{year}_{f'{month+1:02d}'}")
                
        # Custom simple cache: (owner_id, chat_id) -> (timestamp, data)
        if not hasattr(self, '_logs_cache'):
            self._logs_cache = {}
            
        cache_key = (owner_id, chat_id)
        # Cache TTL: 60 seconds (enough to prevent spam clicking)
        if cache_key in self._logs_cache:
            ts, cached_data = self._logs_cache[cache_key]
            if (datetime.utcnow() - ts).total_seconds() < 60:
                logger.info(f"Returning cached logs for {owner_id} -> {chat_id}")
                return cached_data

        import time
        import random

        # Helper function for parallel execution with RETRY logic
        def fetch_sheet_data(sheet_name):
            retries = 3
            for attempt in range(retries):
                try:
                    # Exponential backoff jitter
                    time.sleep(0.5 + random.random() * (attempt + 1))
                    
                    try:
                        ws = self.spreadsheet.worksheet(sheet_name)
                    except gspread.WorksheetNotFound:
                        return []
                        
                    rows = ws.get_all_values()
                    if not rows or len(rows) < 2: return []
                    
                    sheet_msgs = []
                    # Индексы: Time=0, MsgID=1, ChatID=2, OwnerID=3, Dir=4, Type=5, Content=6, FileID=7, Raw=8
                    for row in rows[1:]:
                        if len(row) < 4: continue
                        try:
                            r_owner = str(row[3])
                            r_chat = str(row[2])
                            
                            if str(owner_id) == r_owner and str(chat_id) == r_chat:
                                msg_data = {}
                                raw_json = row[8] if len(row) > 8 else ""
                                if raw_json and raw_json.strip().startswith('{'):
                                    try:
                                        msg_data = json.loads(raw_json)
                                    except: pass
                                
                                col_file_id = row[7] if len(row) > 7 else ""
                                col_text = row[6] if len(row) > 6 else ""
                                col_type = row[5] if len(row) > 5 else "text"
                                col_dir = row[4] if len(row) > 4 else ""
                                is_out = "исх" in col_dir.lower() or "out" in col_dir.lower()
                                
                                final_msg = {
                                    **msg_data,
                                    "message_id": int(row[1]) if row[1].isdigit() else 0,
                                    "chat_id": chat_id,
                                    "owner_id": owner_id,
                                    "timestamp": row[0],
                                    "is_outgoing": is_out,
                                    "content_type": col_type.lower(),
                                    "message_text": col_text if col_text else msg_data.get("message_text", ""),
                                    "file_id": col_file_id if col_file_id else msg_data.get("file_id"),
                                    "source": "google_sheets"
                                }
                                
                                if not final_msg.get("extra_data"):
                                    final_msg["extra_data"] = {}
                                if col_file_id:
                                    final_msg["extra_data"]["file_id"] = col_file_id
                                    
                                sheet_msgs.append(final_msg)
                        except: continue
                    return sheet_msgs
                    
                except Exception as e:
                    if "429" in str(e) or "Quota exceeded" in str(e):
                        logger.warning(f"Rate limit for {sheet_name}, retrying {attempt+1}/{retries}...")
                        time.sleep(2 * (attempt + 1))
                        continue
                    logger.warning(f"Error fetching {sheet_name}: {e}")
                    return []
            return []

        # Запускаем в потоках (IO bound)
        from concurrent.futures import ThreadPoolExecutor
        # STRICTLY LIMIT WORKERS to 3 to avoid hitting 60 req/min limit
        # (3 workers * ~20 sheets is safe with delays)
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = executor.map(fetch_sheet_data, to_check)
            for res in results:
                all_messages.extend(res)
        
        # Save to cache
        self._logs_cache[cache_key] = (datetime.utcnow(), all_messages)
        
        # Cleanup old cache entries (simple)
        if len(self._logs_cache) > 100:
             self._logs_cache = {}
             
        return all_messages
