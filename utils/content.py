"""
Функции анализа содержимого сообщений.
"""

import json
from typing import Dict
from aiogram import types


def get_content_type(message: types.Message) -> Dict:
    """
    Определить тип контента сообщения и извлечь метаданные.
    
    Returns:
        dict с ключами:
        - content_type: тип контента (text, photo, video, ...)
        - text: текст или подпись
        - duration: длительность (для медиа)
        - file_size: размер файла
        - extra_data: дополнительные данные в JSON
    """
    result = {
        "content_type": "unknown",
        "text": None,
        "duration": None,
        "file_size": None,
        "extra_data": None
    }
    
    meta = {}
    
    # Текстовое сообщение
    if message.text:
        result["content_type"] = "text"
        result["text"] = message.text
    
    # Фото
    elif message.photo:
        result["content_type"] = "photo"
        result["text"] = message.caption
        largest = message.photo[-1]  # Берем максимальное разрешение
        result["file_size"] = largest.file_size
        meta["file_id"] = largest.file_id
    
    # Видео
    elif message.video:
        result["content_type"] = "video"
        result["text"] = message.caption
        result["duration"] = message.video.duration
        result["file_size"] = message.video.file_size
        meta["file_id"] = message.video.file_id
    
    # Видеокружок
    elif message.video_note:
        result["content_type"] = "video_note"
        result["duration"] = message.video_note.duration
        result["file_size"] = message.video_note.file_size
        meta["file_id"] = message.video_note.file_id
    
    # Голосовое сообщение
    elif message.voice:
        result["content_type"] = "voice"
        result["duration"] = message.voice.duration
        result["file_size"] = message.voice.file_size
        meta["file_id"] = message.voice.file_id
    
    # Аудиофайл
    elif message.audio:
        result["content_type"] = "audio"
        result["text"] = message.caption
        result["duration"] = message.audio.duration
        result["file_size"] = message.audio.file_size
        meta["file_id"] = message.audio.file_id
        if message.audio.title or message.audio.performer:
            meta["info"] = f"{message.audio.performer or ''} - {message.audio.title or ''}".strip(" -")
    
    # Документ
    elif message.document:
        result["content_type"] = "document"
        result["text"] = message.caption
        result["file_size"] = message.document.file_size
        meta["file_id"] = message.document.file_id
        if message.document.file_name:
            meta["info"] = message.document.file_name
    
    # Стикер
    elif message.sticker:
        result["content_type"] = "sticker"
        result["text"] = message.sticker.emoji
        result["file_size"] = message.sticker.file_size
        meta["file_id"] = message.sticker.file_id
    
    # GIF/Анимация
    elif message.animation:
        result["content_type"] = "animation"
        result["text"] = message.caption
        result["duration"] = message.animation.duration
        result["file_size"] = message.animation.file_size
        meta["file_id"] = message.animation.file_id
    
    # Контакт
    elif message.contact:
        result["content_type"] = "contact"
        contact = message.contact
        meta["info"] = f"{contact.first_name} {contact.last_name or ''}: {contact.phone_number}".strip()
    
    # Геолокация
    elif message.location:
        result["content_type"] = "location"
        loc = message.location
        meta["info"] = f"{loc.latitude}, {loc.longitude}"
    
    # Место
    elif message.venue:
        result["content_type"] = "venue"
        venue = message.venue
        meta["info"] = f"{venue.title}\n{venue.address}"
    
    # Опрос
    elif message.poll:
        result["content_type"] = "poll"
        result["text"] = message.poll.question
        if message.poll.options:
            meta["options"] = [o.text for o in message.poll.options]
    
    # Кубик/Игра
    elif message.dice:
        result["content_type"] = "dice"
        result["text"] = message.dice.emoji
        meta["value"] = str(message.dice.value)
    
    # Игра
    elif message.game:
        result["content_type"] = "game"
        result["text"] = message.game.title
        meta["description"] = message.game.description
    
    # Служебные сообщения (звонки, видеочаты)
    elif result["content_type"] == "unknown":
        if message.video_chat_started:
            result["content_type"] = "service"
            result["text"] = "Начат видеочат/звонок"
        elif message.video_chat_ended:
            result["content_type"] = "service"
            result["text"] = f"Завершен видеочат/звонок ({message.video_chat_ended.duration}с)"
        elif message.video_chat_scheduled:
            result["content_type"] = "service"
            result["text"] = "Запланирован видеочат"
        elif message.successful_payment:
            result["content_type"] = "service"
            result["text"] = "Успешная оплата"
        elif message.connected_website:
            result["content_type"] = "service"
            result["text"] = f"Подключен сайт: {message.connected_website}"
        elif message.content_type:
            result["content_type"] = message.content_type
            result["text"] = message.text or message.caption
            
    if meta:
        result["extra_data"] = json.dumps(meta)
        
    return result
