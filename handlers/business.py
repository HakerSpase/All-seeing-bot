"""
Обработчики бизнес-сообщений.
Подключение/отключение, редактирование, удаление, новые сообщения.
"""

import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from html import escape
from typing import Optional

from aiogram import Router, types, Bot

from config import lang, TIMEZONE
from database import OwnersDB, UsersDB, MessagesDB, message_cache
from utils import format_deleted_message, send_notification, get_content_type
from storage import StorageManager
import traceback

router = Router(name="business")
logger = logging.getLogger(__name__)

# Глобальный менеджер хранилища (инициализируется в main.py)
storage_mgr: Optional[StorageManager] = None


def set_storage_manager(manager: StorageManager):
    """Установить менеджер хранилища (вызывается из main.py)."""
    global storage_mgr
    storage_mgr = manager


@router.business_connection()
async def handle_business_connection(event: types.BusinessConnection):
    """Обработчик подключения/отключения бота к Telegram Business."""
    user_id = event.user.id
    user_fullname = event.user.full_name
    connection_id = event.id
    
    if event.is_enabled:
        # Подключение - сначала загружаем аватарку
        avatar_file_id = None
        try:
            photos = await event.bot.get_user_profile_photos(user_id, limit=1)
            if photos.total_count > 0:
                avatar_file_id = photos.photos[0][0].file_id
        except Exception as e:
            logger.warning(f"Не удалось получить аватарку владельца {user_id}: {e}")
        
        await asyncio.to_thread(
            OwnersDB.add,
            user_id=user_id,
            business_connection_id=connection_id,
            user_fullname=user_fullname,
            username=event.user.username,
            avatar_file_id=avatar_file_id
        )
        logger.info(f"Владелец подключен: {user_fullname} ({user_id})")
        
        try:
            await event.bot.send_message(
                user_id,
                lang.OWNER_CONNECTED_FORMAT.format(user_fullname=user_fullname),
                parse_mode='html'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки подтверждения {user_id}: {e}")
    else:
        # Отключение
        await asyncio.to_thread(OwnersDB.delete, user_id=user_id)
        logger.info(f"Владелец отключен: {user_fullname} ({user_id})")
        
        try:
            await event.bot.send_message(
                user_id,
                lang.OWNER_DISCONNECTED_FORMAT,
                parse_mode='html'
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления об отключении {user_id}: {e}")


# Хелпер для извлечения file_id из extra_data (str или dict)
def extract_file_id(extra_data) -> Optional[str]:
    if not extra_data:
        return None
    try:
        data = extra_data
        if isinstance(data, str) and data.startswith('{'):
            data = json.loads(data)
        
        if isinstance(data, dict):
            return data.get("file_id")
    except:
        pass
    return None

@router.edited_business_message()
async def handle_edited_business_message(message: types.Message):
    """Обработчик редактирования сообщения."""
    connection_id = message.business_connection_id
    owner = await asyncio.to_thread(OwnersDB.get_by_connection_id, connection_id)
    if not owner:
        logger.warning(f"Владелец не найден для подключения: {connection_id}")
        return
    
    owner_id = owner["user_id"]
    chat_id = message.chat.id
    is_outgoing = message.from_user.id != message.chat.id
    
    # Получаем сохраненное сообщение (сначала кеш, потом БД)
    stored = message_cache.get(owner_id=owner_id, chat_id=chat_id, message_id=message.message_id)
    if not stored:
        stored = await asyncio.to_thread(MessagesDB.get, owner_id=owner_id, chat_id=chat_id, message_id=message.message_id)
    if not stored:
        logger.debug(f"Сообщение не найдено для редактирования: {message.message_id}")
        return
        
    # Проверяем настройки для исходящих сообщений
    if is_outgoing:
        notify_on_edit = owner.get("notify_on_edit", False)
        if not notify_on_edit:
            return
    
    # Получаем новый тип контента и текст
    new_content_info = get_content_type(message)
    new_type = new_content_info["content_type"]
    new_text = new_content_info["text"] or "[пусто]"
    
    old_type = stored["content_type"]
    old_text = stored["message_text"] or "[пусто]"
    
    # Сравниваем file_id для проверки изменения самого медиа (фото -> другое фото)
    media_changed = False
    
    new_extra = new_content_info.get("extra_data")
    old_extra = stored.get("extra_data")
    
    new_file_id = extract_file_id(new_extra)
    old_file_id = extract_file_id(old_extra)
            
    # Если и там и там есть file_id, сравниваем их
    if new_file_id and old_file_id and new_file_id != old_file_id:
        media_changed = True
    
    # Проверяем, изменилось ли что-то (тип, текст или сам файл медиа)
    type_changed = new_type != old_type
    text_changed = new_text != old_text
    
    if not type_changed and not text_changed and not media_changed:
        return
    
    # Форматируем время
    try:
        message_timestamp = datetime.fromisoformat(stored["timestamp"].replace('Z', '+00:00'))
        message_timestamp_local = message_timestamp.astimezone(TIMEZONE)
        timestamp_formatted = message_timestamp_local.strftime('%d/%m/%y %H:%M')
    except:
        timestamp_formatted = "???"
    
    # Определяем ссылки
    username = None
    if is_outgoing:
        user_fullname_escaped = "Вы"
        user_link = f"tg://user?id={chat_id}" # Для себя ссылка не так важна
        client_user = await asyncio.to_thread(UsersDB.get, user_id=chat_id, owner_id=owner_id)
        if client_user:
            username = client_user.get("username")
    else:
        user_fullname_escaped = escape(message.from_user.full_name)
        username = message.from_user.username
        user_link = f"https://t.me/{username}" if username else f"tg://user?id={message.from_user.id}"
        
    # Формируем сообщение
    # Если изменился только медиа-файл (без текста), используем специальный формат
    if (type_changed or media_changed) and not text_changed:
        # Специальный формат для изменения медиа
        old_type_name = lang.CONTENT_TYPE_NAMES.get(old_type, old_type)
        new_type_name = lang.CONTENT_TYPE_NAMES.get(new_type, new_type)
        
        if type_changed:
            change_description = f"<b>Тип изменён:</b> {old_type_name} ➡️ {new_type_name}"
        else:
            # media_changed но тип тот же (например, фото на другое фото)
            change_description = f"<b>Медиа обновлено:</b> {new_type_name} заменено на другое"
        
        msg = (
            f"<b>ИЗМЕНЕНО</b>\n"
            f"<a href='{user_link}'>{user_fullname_escaped}</a> | {timestamp_formatted}\n\n"
            f"{change_description}"
        )
        
        # Если есть подпись/текст, добавляем
        if new_text != "[пусто]":
            msg += f"\n\n<b>Подпись:</b>\n<blockquote>{escape(new_text)}</blockquote>"
        
        # Отправляем текстовое уведомление
        await send_notification(message.bot, owner_id, msg)
        
        # Теперь отправляем визуальное сравнение медиа (если оба file_id есть)
        async def send_media_by_type(bot, user_id, file_id, content_type, caption):
            """Хелпер для отправки медиа по типу."""
            try:
                if content_type == "photo":
                    await bot.send_photo(user_id, file_id, caption=caption, parse_mode='html')
                elif content_type == "video":
                    await bot.send_video(user_id, file_id, caption=caption, parse_mode='html')
                elif content_type == "animation":
                    await bot.send_animation(user_id, file_id, caption=caption, parse_mode='html')
                elif content_type == "document":
                    await bot.send_document(user_id, file_id, caption=caption, parse_mode='html')
                elif content_type == "sticker":
                    await send_notification(bot, user_id, caption)
                    await bot.send_sticker(user_id, file_id)
                elif content_type == "video_note":
                    await send_notification(bot, user_id, caption)
                    await bot.send_video_note(user_id, file_id)
                elif content_type == "voice":
                    await bot.send_voice(user_id, file_id, caption=caption, parse_mode='html')
                elif content_type == "audio":
                    await bot.send_audio(user_id, file_id, caption=caption, parse_mode='html')
                else:
                    await send_notification(bot, user_id, f"{caption}\n<i>[{content_type}]</i>")
                return True
            except Exception as e:
                logger.warning(f"Ошибка отправки медиа сравнения: {e}")
                return False
        
        # Отправляем старое медиа (Было)
        if old_file_id:
            await send_media_by_type(message.bot, owner_id, old_file_id, old_type, "<b>Было:</b>")
        
        # Отправляем новое медиа (Стало)
        if new_file_id:
            await send_media_by_type(message.bot, owner_id, new_file_id, new_type, "<b>Стало:</b>")
            
    else:
        # Определяем: это изменение обычного текста или подписи к медиа?
        is_caption_edit = new_type != "text"  # Если тип не "text", значит это подпись к медиа
        
        if is_caption_edit:
            # Специальный формат для изменения подписи к медиа
            media_type_name = lang.CONTENT_TYPE_NAMES.get(new_type, new_type)
            
            msg = (
                f"<b>ИЗМЕНЕНО</b>\n"
                f"<a href='{user_link}'>{user_fullname_escaped}</a> | {timestamp_formatted}\n\n"
                f"<b>Подпись к {media_type_name} изменена:</b>\n\n"
                f"<b>Было:</b>\n"
                f"<blockquote>{escape(old_text) if old_text != '[пусто]' else '<i>пусто</i>'}</blockquote>\n\n"
                f"<b>Стало:</b>\n"
                f"<blockquote>{escape(new_text) if new_text != '[пусто]' else '<i>пусто</i>'}</blockquote>"
            )
        else:
            # Стандартный формат для текстовых сообщений
            msg = lang.EDITED_MESSAGE_FORMAT.format(
                user_link=user_link,
                user_fullname_escaped=user_fullname_escaped,
                timestamp=timestamp_formatted,
                old_text=escape(old_text) if old_text != "[пусто]" else "<i>пусто</i>",
                new_text=escape(new_text) if new_text != "[пусто]" else "<i>пусто</i>"
            )
        
        # Добавляем инфо о смене типа/медиа если было (в дополнение к тексту)
        extra_info = ""
        if type_changed:
            extra_info = f"\n\n<b>Инфо:</b> Тип медиа изменён ({lang.CONTENT_TYPE_NAMES.get(old_type, old_type)} ➡️ {lang.CONTENT_TYPE_NAMES.get(new_type, new_type)})"
        elif media_changed:
            extra_info = f"\n\n<b>Инфо:</b> Медиа вложение также обновлено"
            
        msg += extra_info

        await send_notification(message.bot, owner_id, msg)
        
        # Если медиа изменилось вместе с текстом, тоже покажем визуальное сравнение
        if media_changed and old_file_id and new_file_id:
            try:
                # Отправляем старое
                if old_type == "photo":
                    await message.bot.send_photo(owner_id, old_file_id, caption="<b>Было:</b>", parse_mode='html')
                elif old_type == "video":
                    await message.bot.send_video(owner_id, old_file_id, caption="<b>Было:</b>", parse_mode='html')
                elif old_type == "document":
                    await message.bot.send_document(owner_id, old_file_id, caption="<b>Было:</b>", parse_mode='html')
                # Отправляем новое
                if new_type == "photo":
                    await message.bot.send_photo(owner_id, new_file_id, caption="<b>Стало:</b>", parse_mode='html')
                elif new_type == "video":
                    await message.bot.send_video(owner_id, new_file_id, caption="<b>Стало:</b>", parse_mode='html')
                elif new_type == "document":
                    await message.bot.send_document(owner_id, new_file_id, caption="<b>Стало:</b>", parse_mode='html')
            except Exception as e:
                logger.debug(f"Не удалось отправить медиа сравнение: {e}")
    
    # Обновляем сообщение в кеше (мгновенно) и БД (асинхронно)
    message_cache.update(
        owner_id=owner_id,
        chat_id=chat_id,
        message_id=message.message_id,
        message_text=new_text,
        content_type=new_type,
        extra_data=new_content_info["extra_data"]
    )
    asyncio.create_task(asyncio.to_thread(
        MessagesDB.update,
        owner_id=owner_id,
        chat_id=chat_id,
        message_id=message.message_id,
        message_text=new_text,
        content_type=new_type,
        extra_data=new_content_info["extra_data"]
    ))


@router.deleted_business_messages()
async def handle_deleted_business_messages(event: types.BusinessMessagesDeleted):
    """Обработчик удаления сообщений (поддержка массового удаления)."""
    chat_id = event.chat.id
    connection_id = event.business_connection_id
    
    owner = await asyncio.to_thread(OwnersDB.get_by_connection_id, connection_id)
    if not owner:
        return
    
    owner_id = owner["user_id"]
    
    # 1. Собираем сообщения
    deleted_messages = []
    notify_on_edit = owner.get("notify_on_edit", False)
    
    for msg_id in event.message_ids:
        # 0. В ЛЮБОМ СЛУЧАЕ помечаем как удаленное в БД (Soft Delete)
        # Это критично, чтобы статус обновился даже если мы не нашли сообщение для уведомления
        await asyncio.to_thread(MessagesDB.delete, owner_id=owner_id, chat_id=chat_id, message_id=msg_id)
        message_cache.delete(owner_id=owner_id, chat_id=chat_id, message_id=msg_id)

        # Сначала кеш, потом БД (для уведомления)
        stored = message_cache.get(owner_id=owner_id, chat_id=chat_id, message_id=msg_id)
        if not stored:
             stored = await asyncio.to_thread(MessagesDB.get, owner_id=owner_id, chat_id=chat_id, message_id=msg_id)
        
        if not stored:
            continue
            
        is_outgoing = stored.get("is_outgoing", False)
        if is_outgoing and not notify_on_edit:
            continue
            
        deleted_messages.append(stored)

    if not deleted_messages:
        return

    # Бэкапим
    if storage_mgr:
        await storage_mgr.log_deleted_messages(deleted_messages)

    # 2. Подготовка общих данных
    chat_name = escape(event.chat.full_name or event.chat.first_name or str(chat_id))
    user_link = f"tg://user?id={chat_id}"
    client_user = await asyncio.to_thread(UsersDB.get, user_id=chat_id, owner_id=owner_id)
    if client_user and client_user.get("username"):
        user_link = f"https://t.me/{client_user.get('username')}"

    # Хелперы
    def get_time_str(iso_time):
        try:
            dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
            return dt.astimezone(TIMEZONE).strftime('%H:%M')
        except:
            return "?"
            
    def get_full_date_str(iso_time):
        try:
            dt = datetime.fromisoformat(iso_time.replace('Z', '+00:00'))
            return dt.astimezone(TIMEZONE).strftime('%d/%m/%y %H:%M')
        except:
            return "???"

    # === ЛОГИКА ОТПРАВКИ ===
    
    async def send_text_batch(batch):
        if not batch: return
        
        # Если одно - отправляем красиво как одиночное
        if len(batch) == 1:
            msg_data = batch[0]
            is_outgoing = msg_data.get("is_outgoing", False)
            timestamp_fmt = get_full_date_str(msg_data["timestamp"])
            fullname = "Вы" if is_outgoing else escape(event.chat.full_name or "Client")
            
            msg = format_deleted_message(
                content_type="text",
                message_text=msg_data["message_text"],
                duration=None,
                extra_data=None,
                user_fullname_escaped=fullname,
                user_id=chat_id,
                user_link=user_link,
                timestamp=timestamp_fmt,
                is_outgoing=is_outgoing
            )
            if is_outgoing:
                msg = msg.replace("\n", f"\n💬 <b>Кому:</b> {chat_name}\n", 1)
            await send_notification(event.bot, owner_id, msg)
        else:
            # Сводка текстов
            has_outgoing = any(m.get("is_outgoing") for m in batch)
            header = f"<b>МАССОВОЕ УДАЛЕНИЕ (Текст: {len(batch)})</b>"
            user_block = f"💬 <b>Кому:</b> {chat_name}" if has_outgoing else f"👤 <a href='{user_link}'>{chat_name}</a>"
            summary = f"{header}\n{user_block}\n\n"
            for i, item in enumerate(batch, 1):
                t_str = get_time_str(item["timestamp"])
                txt = escape(item["message_text"] or "[без текста]")
                summary += f"<b>{i}. {t_str}</b>\n<blockquote>{txt}</blockquote>\n\n"
            await send_notification(event.bot, owner_id, summary)

    async def send_media_item(msg_data):
        is_outgoing = msg_data.get("is_outgoing", False)
        timestamp_fmt = get_full_date_str(msg_data["timestamp"])
        fullname = "Вы" if is_outgoing else escape(event.chat.full_name or "Client")
        
        msg = format_deleted_message(
            content_type=msg_data["content_type"],
            message_text=msg_data["message_text"],
            duration=msg_data.get("media_duration"),
            extra_data=msg_data.get("extra_data"),
            user_fullname_escaped=fullname,
            user_id=chat_id,
            user_link=user_link,
            timestamp=timestamp_fmt,
            is_outgoing=is_outgoing
        )
        
        if is_outgoing:
            msg = msg.replace("\n", f"\n💬 <b>Кому:</b> {chat_name}\n", 1)
            
        file_id = extract_file_id(msg_data.get("extra_data"))
            
        sent = False
        if file_id:
            try:
                ct = msg_data["content_type"]
                if ct == "sticker":
                    await send_notification(event.bot, owner_id, msg)
                    await event.bot.send_sticker(owner_id, file_id)
                elif ct == "video_note":
                    await send_notification(event.bot, owner_id, msg)
                    await event.bot.send_video_note(owner_id, file_id)
                elif ct == "photo":
                    await event.bot.send_photo(owner_id, file_id, caption=msg, parse_mode='html')
                elif ct == "video":
                    await event.bot.send_video(owner_id, file_id, caption=msg, parse_mode='html')
                elif ct == "animation":
                    await event.bot.send_animation(owner_id, file_id, caption=msg, parse_mode='html')
                elif ct == "document":
                    await event.bot.send_document(owner_id, file_id, caption=msg, parse_mode='html')
                elif ct == "audio":
                    await event.bot.send_audio(owner_id, file_id, caption=msg, parse_mode='html')
                elif ct == "voice":
                    await event.bot.send_voice(owner_id, file_id, caption=msg, parse_mode='html')
                else:
                    await send_notification(event.bot, owner_id, msg)
                sent = True
            except Exception as e:
                logger.warning(f"Ошибка отправки медиа {msg_data['message_id']}: {e}")
        
        if not sent:
             await send_notification(event.bot, owner_id, msg)

    # 3. Основной цикл сортировки и отправки
    text_buffer = []
    
    # Переменные для группировки стикеров
    current_sticker_id = None
    current_sticker_count = 0
    current_sticker_sample = None
    
    async def flush_sticker_group():
        nonlocal current_sticker_id, current_sticker_count, current_sticker_sample
        if current_sticker_count > 0 and current_sticker_sample:
            if current_sticker_count > 1:
                # Группа свернутая
                smpl = current_sticker_sample
                is_outline = smpl.get("is_outgoing", False)
                ts_fmt = get_full_date_str(smpl["timestamp"])
                fname = "Вы" if is_outline else escape(event.chat.full_name or "Client")
                
                header_txt = f"<b>УДАЛЕНО ({current_sticker_count} стикеров)</b>"
                txt_msg = (
                    f"{header_txt}\n"
                    f"<a href='{user_link}'>{fname}</a> | {ts_fmt}\n\n"
                    f"<b>Тип:</b> Одинаковые стикеры (x{current_sticker_count})"
                )
                if is_outline:
                     txt_msg = txt_msg.replace("\n", f"\n💬 <b>Кому:</b> {chat_name}\n", 1)
                
                await send_notification(event.bot, owner_id, txt_msg)
                # Отправляем сам стикер напрямую (без дополнительного уведомления)
                file_id = extract_file_id(smpl.get("extra_data"))
                if file_id:
                    try:
                        await event.bot.send_sticker(owner_id, file_id)
                    except Exception as e:
                        logger.warning(f"Ошибка отправки стикера группы: {e}")
            else:
                # Один стикер - отправляем как обычно
                await send_media_item(current_sticker_sample)
                
        # Сброс
        current_sticker_id = None
        current_sticker_count = 0
        current_sticker_sample = None
        
    for msg in deleted_messages:
        ct = msg["content_type"]
        
        if ct == "sticker":
            # Сначала скидываем накопленные тексты
            if text_buffer:
                await send_text_batch(text_buffer)
                text_buffer = []
            
            # Получаем file_id
            fid = extract_file_id(msg.get("extra_data"))
            
            # Сравниваем с предыдущим
            if fid and fid == current_sticker_id:
                # Тот же самый стикер
                current_sticker_count += 1
            else:
                # Другой стикер (или первый) - скидываем предыдущую группу
                await flush_sticker_group()
                
                # Начинаем новую
                current_sticker_id = fid
                current_sticker_count = 1
                current_sticker_sample = msg
                
        else: # Не стикер
            # Скидываем стикеры если были
            await flush_sticker_group()
            
            if ct == "text":
                text_buffer.append(msg)
            else:
                # Медиа - скидываем тексты
                await send_text_batch(text_buffer)
                text_buffer = []
                # Отправляем медиа
                await send_media_item(msg)
            
    # Отправляем остатки
    await flush_sticker_group()
    await send_text_batch(text_buffer)
    
    # 4. Удаляем из БД
    # Удаление из БД перемещено в начало цикла по ID, чтобы гарантировать удаление
    # даже если сообщения нет в кеше/базе для уведомления.


@router.business_message()
async def handle_business_message(message: types.Message):
    """Обработчик всех бизнес-сообщений (входящих и исходящих)."""
    connection_id = message.business_connection_id
    owner = await asyncio.to_thread(OwnersDB.get_by_connection_id, connection_id)
    if not owner:
        logger.warning(f"Владелец не найден для подключения: {connection_id}")
        return
    
    owner_id = owner["user_id"]
    chat_id = message.chat.id
    
    # Определяем направление
    is_outgoing = message.from_user.id != message.chat.id
    
    # Для входящих — отслеживаем нового клиента
    if not is_outgoing:
        user_id = message.from_user.id
        user_fullname = message.from_user.full_name
        user_fullname_escaped = escape(user_fullname)
        
        # Проверяем Premium (None -> False)
        is_premium = bool(message.from_user.is_premium)
        
        user_record = await asyncio.to_thread(UsersDB.get, user_id=user_id, owner_id=owner_id)
        
        if not user_record:
            # Новый пользователь
            # Пробуем получить аватарку
            avatar_file_id = None
            try:
                photos = await message.bot.get_user_profile_photos(user_id, limit=1)
                if photos.total_count > 0:
                    avatar_file_id = photos.photos[0][0].file_id # Берем маленькую
            except Exception as e:
                logger.warning(f"Failed to get profile photo for {user_id}: {e}")

            await asyncio.to_thread(
                UsersDB.add, 
                user_id=user_id, 
                owner_id=owner_id, 
                user_fullname=user_fullname, 
                username=message.from_user.username,
                is_premium=is_premium,
                avatar_file_id=avatar_file_id
            )
            
            if message.from_user.username:
                user_link = f"https://t.me/{message.from_user.username}"
            else:
                user_link = f"tg://user?id={user_id}"
            
            msg = lang.NEW_USER_MESSAGE_FORMAT.format(
                user_fullname_escaped=user_fullname_escaped,
                user_id=user_id,
                user_link=user_link
            )
            
            if is_premium:
                msg += "\n💎 <b>Telegram Premium</b>"
                
            await send_notification(message.bot, owner_id, msg)
        else:
            # Пользователь есть, проверяем изменился ли статус премиум
            db_premium = user_record.get("is_premium")
            updates = {}
            if bool(db_premium) != is_premium:
                updates["is_premium"] = is_premium
            
            # Обновляем аватарку раз в сутки или если её нет
            last_avatar_check = user_record.get("avatar_updated_at")
            should_check_avatar = True
            
            if last_avatar_check:
                try:
                    last_check_dt = datetime.fromisoformat(last_avatar_check.replace('Z', '+00:00'))
                    if datetime.now(timezone.utc) - last_check_dt < timedelta(hours=24):
                        should_check_avatar = False
                except:
                    pass
            
            if should_check_avatar:
                try:
                    photos = await message.bot.get_user_profile_photos(user_id, limit=1)
                    if photos.total_count > 0:
                        new_avatar = photos.photos[0][0].file_id
                        # Обновляем только если аватарка изменилась или её не было
                        if new_avatar != user_record.get("avatar_file_id"):
                            updates["avatar_file_id"] = new_avatar
                    updates["avatar_updated_at"] = datetime.now(timezone.utc).isoformat()
                except: pass
            
            if updates:
                await asyncio.to_thread(UsersDB.update, user_id=user_id, owner_id=owner_id, **updates)
                logger.info(f"Updated User {user_id}: {list(updates.keys())}")
    
    # Извлекаем информацию о контенте
    content_info = get_content_type(message)
    
    # Время сообщения
    message_datetime_utc = message.date.replace(tzinfo=timezone.utc)
    timestamp_iso = message_datetime_utc.isoformat()
    
    # Дополнительные данные: reply_to
    reply_to_message_id = None
    if message.reply_to_message:
        reply_to_message_id = message.reply_to_message.message_id
    
    # Подготавливаем данные
    msg_data = {
        "owner_id": owner_id,
        "chat_id": chat_id,
        "message_id": message.message_id,
        "reply_to_message_id": reply_to_message_id,
        "timestamp": timestamp_iso,
        "sender_id": message.from_user.id,
        "sender_fullname": message.from_user.full_name,
        "sender_username": message.from_user.username,
        "is_outgoing": is_outgoing,
        "content_type": content_info["content_type"],
        "message_text": content_info["text"],
        "media_duration": content_info["duration"],
        "media_file_size": content_info["file_size"],
        "extra_data": content_info["extra_data"],
        "file_id": extract_file_id(content_info["extra_data"])
    }
    
    # Сохраняем в кеш СРАЗУ (мгновенно доступно для edit/delete)
    message_cache.set(
        owner_id=owner_id,
        chat_id=chat_id,
        message_id=message.message_id,
        data=msg_data
    )
    
    # Сохраняем в Supabase (асинхронно)
    asyncio.create_task(asyncio.to_thread(
        MessagesDB.add,
        **{k: v for k, v in msg_data.items() if k != "file_id"}
    ))
    
@router.edited_business_message()
async def handle_business_message_edit(message: types.Message):
    """Обработка редактирования сообщений (история изменений)."""
    connection_id = message.business_connection_id
    owner = await asyncio.to_thread(OwnersDB.get_by_connection_id, connection_id)
    if not owner: return
    
    owner_id = owner["user_id"]
    chat_id = message.chat.id
    message_id = message.message_id
    
    # 1. Получаем текущее сообщение из БД
    current_msg = await asyncio.to_thread(MessagesDB.get, owner_id, chat_id, message_id)
    
    # Если сообщения нет в базе (старое), обрабатываем как новое, но с пометкой?
    # Лучше просто обработать как новое, чтобы оно появилось в базе
    if not current_msg:
        await handle_business_message(message)
        return

    # 2. Формируем запись истории
    old_text = current_msg.get("message_text")
    old_timestamp = current_msg.get("timestamp")
    
    # Если это просто обновление статуса (без изменения текста), пропускаем?
    # Telegram присылает edited_message только при изменении контента
    
    edit_entry = {
         # Если old_text None, значит текста не было
        "message_text": old_text,
        "timestamp": old_timestamp
    }
    
    current_history = current_msg.get("edit_history") or []
    # Если history хранит список, добавляем
    if isinstance(current_history, list):
        current_history.append(edit_entry)
    else:
        current_history = [edit_entry]
    
    # 3. Обновляем сообщение новыми данными
    content_info = get_content_type(message)
    message_datetime_utc = message.edit_date.replace(tzinfo=timezone.utc)
    new_timestamp_iso = message_datetime_utc.isoformat()
    
    updates = {
        "message_text": content_info["text"],
        "timestamp": new_timestamp_iso,
        "edit_history": current_history,
        "content_type": content_info["content_type"],
        "extra_data": content_info["extra_data"]
    }
    
    await asyncio.to_thread(MessagesDB.update, owner_id=owner_id, chat_id=chat_id, message_id=message_id, **updates)
    
    # Обновляем кеш
    new_msg_data = {**current_msg, **updates}
    message_cache.set(owner_id, chat_id, message_id, new_msg_data)
    
    # Оповещение если нужно
    if owner.get("notify_on_edit"):
         # Формируем уведомление об изменении
         notification_text = f"✏️ <b>ИЗМЕНЕНО</b>\n"
         notification_text += f"Было: {escape(old_text or '[нет]')}\n"
         notification_text += f"Стало: {escape(content_info['text'] or '[нет]')}"
         # Можно отправить, но юзер просил "дизайн", это для админки.
         # В телеграм можно отправить уведомление
         pass
