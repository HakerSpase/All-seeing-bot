"""
Обработчики бизнес-сообщений.
Подключение/отключение, редактирование, удаление, новые сообщения.
"""

import json
import asyncio
import logging
from datetime import datetime, timezone
from html import escape
from typing import Optional

from aiogram import Router, types, Bot

from config import lang, TIMEZONE
from database import OwnersDB, UsersDB, MessagesDB, message_cache
from utils import format_deleted_message, send_notification, get_content_type
from storage import StorageManager

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
        # Подключение
        await asyncio.to_thread(
            OwnersDB.add,
            user_id=user_id,
            business_connection_id=connection_id,
            user_fullname=user_fullname,
            username=event.user.username
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
    
    new_file_id = None
    old_file_id = None
    
    if new_extra:
        try:
            new_file_id = json.loads(new_extra).get("file_id")
        except:
            pass
            
    if old_extra:
        try:
            # old_extra может быть уже dict если мы неаккуратно сохранили, или str
            if isinstance(old_extra, str) and old_extra.startswith('{'):
                old_file_id = json.loads(old_extra).get("file_id")
        except:
            pass
            
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
    change_info = ""
    
    if type_changed:
        change_info += f"\n🔄 <b>Тип изменён:</b> {old_type} ➡️ {new_type}"
    elif media_changed:
        change_info += f"\n🔄 <b>Медиа изменено</b> ({new_type})"
        
    if text_changed:
        if type_changed or media_changed:
            change_info += f"\n✏️ <b>Текст изменён:</b>\n🔴 <s>{old_text}</s>\n🟢 {new_text}"
        else:
            # Только текст изменился
            change_info += f"\n🔴 <s>{old_text}</s>\n🟢 {new_text}"
    elif (type_changed or media_changed) and not text_changed:
         change_info += f"\n📝 <b>Текст:</b> {new_text}"

    header = "📝 <b>ИЗМЕНЕНО (ВЫ)</b>" if is_outgoing else "✏️ <b>ИЗМЕНЕНО</b>"
    
    # Для исходящих показываем кому писали, для входящих - от кого
    if is_outgoing:
        # Получаем имя получателя из чата
        chat_name = escape(message.chat.full_name or message.chat.first_name or str(chat_id))
        recipient_info = f"\n💬 <b>Кому:</b> {chat_name}"
    else:
        recipient_info = ""
    
    msg = (
        f"{header}\n"
        f"👤 <a href='{user_link}'>{user_fullname_escaped}</a>"
        f"{recipient_info}\n"
        f"🕒 {timestamp_formatted}"
        f"{change_info}"
    )
    
    await send_notification(message.bot, owner_id, msg)
    
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
    notify_on_edit = owner.get("notify_on_edit", False)
    
    # Собираем информацию о всех удаленных сообщениях
    deleted_messages = []
    
    for msg_id in event.message_ids:
        # Сначала кеш, потом БД
        stored = message_cache.get(owner_id=owner_id, chat_id=chat_id, message_id=msg_id)
        if not stored:
            stored = await asyncio.to_thread(MessagesDB.get, owner_id=owner_id, chat_id=chat_id, message_id=msg_id)
        if not stored:
            continue
            
        is_outgoing = stored.get("is_outgoing", False)
        if is_outgoing and not notify_on_edit:
            # Просто удаляем из кеша и БД без уведомления
            message_cache.delete(owner_id=owner_id, chat_id=chat_id, message_id=msg_id)
            await asyncio.to_thread(MessagesDB.delete, owner_id=owner_id, chat_id=chat_id, message_id=msg_id)
            continue
            
        deleted_messages.append(stored)

    if not deleted_messages:
        return

    # Бэкапим в Google Sheets перед удалением (чтобы сохранить историю)
    if storage_mgr:
        await storage_mgr.log_deleted_messages(deleted_messages)

    # Если сообщений много (>1), шлём сводку
    if len(deleted_messages) > 1:
        chat_name = escape(event.chat.full_name or event.chat.first_name or str(chat_id))
        
        # Проверяем, есть ли среди них исходящие
        has_outgoing = any(m.get("is_outgoing") for m in deleted_messages)
        
        summary = f"🗑 <b>МАССОВОЕ УДАЛЕНИЕ ({len(deleted_messages)})</b>\n"
        if has_outgoing:
            summary += f"💬 <b>Кому:</b> {chat_name}\n\n"
        else:
            summary += f"👤 <b>От:</b> {chat_name}\n\n"
        
        for i, msg_data in enumerate(deleted_messages, 1):
            msg_type = msg_data.get("content_type", "text")
            text = msg_data.get("message_text") or "[без текста]"
            time_str = "?"
            if msg_data.get("timestamp"):
                try:
                    dt = datetime.fromisoformat(msg_data["timestamp"].replace('Z', '+00:00'))
                    time_str = dt.astimezone(TIMEZONE).strftime('%H:%M')
                except:
                    pass
            
            # Обрезаем длинный текст
            if len(text) > 50:
                text = text[:50] + "..."
                
            summary += f"{i}. <code>{time_str}</code> [{msg_type}] {escape(text)}\n"
        
        await send_notification(event.bot, owner_id, summary)
        
        # Удаляем из кеша и БД
        for msg in deleted_messages:
            message_cache.delete(owner_id=owner_id, chat_id=chat_id, message_id=msg["message_id"])
            await asyncio.to_thread(MessagesDB.delete, owner_id=owner_id, chat_id=chat_id, message_id=msg["message_id"])
            
    else:
        # Если одно сообщение — используем старый красивый формат с медиа
        stored = deleted_messages[0]
        msg_id = stored["message_id"]
        is_outgoing = stored.get("is_outgoing", False)
        
        # Форматируем время
        try:
            message_timestamp = datetime.fromisoformat(stored["timestamp"].replace('Z', '+00:00'))
            message_timestamp_local = message_timestamp.astimezone(TIMEZONE)
            timestamp_formatted = message_timestamp_local.strftime('%d/%m/%y %H:%M')
        except:
            timestamp_formatted = "???"

        # Приводим к формату для user_link
        user_link = f"tg://user?id={chat_id}" # Simplification for deleted
        
        # Формируем текст
        msg = format_deleted_message(
            content_type=stored["content_type"],
            message_text=stored["message_text"],
            duration=stored["media_duration"],
            extra_data=stored["extra_data"],
            user_fullname_escaped="Вы" if is_outgoing else escape(event.chat.full_name or "Client"),
            user_id=chat_id,
            user_link=user_link,
            timestamp=timestamp_formatted,
            is_outgoing=is_outgoing
        )
        
        # Для исходящих добавляем кому было адресовано
        if is_outgoing:
            chat_name = escape(event.chat.full_name or event.chat.first_name or str(chat_id))
            msg = msg.replace("\n", f"\n💬 <b>Кому:</b> {chat_name}\n", 1)
        
        # Пытаемся отправить медиа, если есть file_id
        sent_media = False
        extra_data_raw = stored.get("extra_data")
        file_id = None
        if extra_data_raw and extra_data_raw.startswith('{'):
            try:
                file_id = json.loads(extra_data_raw).get("file_id")
            except: 
                pass
                
        if file_id:
            try:
                content_type = stored["content_type"]
                # Упрощенная логика отправки медиа (как была)
                if content_type == "photo":
                    await event.bot.send_photo(owner_id, file_id, caption=msg, parse_mode='html')
                    sent_media = True
                elif content_type == "video":
                    await event.bot.send_video(owner_id, file_id, caption=msg, parse_mode='html')
                    sent_media = True
                elif content_type == "animation":
                    await event.bot.send_animation(owner_id, file_id, caption=msg, parse_mode='html')
                    sent_media = True
                elif content_type == "document":
                    await event.bot.send_document(owner_id, file_id, caption=msg, parse_mode='html')
                    sent_media = True
                elif content_type == "audio":
                    await event.bot.send_audio(owner_id, file_id, caption=msg, parse_mode='html')
                    sent_media = True
                elif content_type == "voice":
                    await event.bot.send_voice(owner_id, file_id, caption=msg, parse_mode='html')
                    sent_media = True
                elif content_type == "sticker":
                    await send_notification(event.bot, owner_id, msg)
                    await event.bot.send_sticker(owner_id, file_id)
                    sent_media = True
                elif content_type == "video_note":
                    await send_notification(event.bot, owner_id, msg)
                    await event.bot.send_video_note(owner_id, file_id)
                    sent_media = True
                    
            except Exception as e:
                logger.warning(f"Не удалось переслать медиа ({stored['content_type']}): {e}")
        
        if not sent_media:
            await send_notification(event.bot, owner_id, msg)
            
        message_cache.delete(owner_id=owner_id, chat_id=chat_id, message_id=msg_id)
        await asyncio.to_thread(MessagesDB.delete, owner_id=owner_id, chat_id=chat_id, message_id=msg_id)


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
        
        user_record = await asyncio.to_thread(UsersDB.get, user_id=user_id, owner_id=owner_id)
        if not user_record:
            await asyncio.to_thread(UsersDB.add, user_id=user_id, owner_id=owner_id, user_fullname=user_fullname, username=message.from_user.username)
            
            if message.from_user.username:
                user_link = f"https://t.me/{message.from_user.username}"
            else:
                user_link = f"tg://user?id={user_id}"
            
            msg = lang.NEW_USER_MESSAGE_FORMAT.format(
                user_fullname_escaped=user_fullname_escaped,
                user_id=user_id,
                user_link=user_link
            )
            await send_notification(message.bot, owner_id, msg)
    
    # Извлекаем информацию о контенте
    content_info = get_content_type(message)
    
    # Время сообщения
    message_datetime_utc = message.date.replace(tzinfo=timezone.utc)
    timestamp_iso = message_datetime_utc.isoformat()
    
    # Подготавливаем данные
    msg_data = {
        "owner_id": owner_id,
        "chat_id": chat_id,
        "message_id": message.message_id,
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
        "file_id": json.loads(content_info["extra_data"]).get("file_id") if content_info["extra_data"] and "file_id" in content_info["extra_data"] else None
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
    
    # Логируем в Google Sheets
    if storage_mgr:
        await storage_mgr.add_message(msg_data)
