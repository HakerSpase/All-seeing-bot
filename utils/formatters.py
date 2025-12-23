"""
Вспомогательные функции форматирования.
"""

import json
from typing import Optional
from html import escape

from config import lang


def format_duration(seconds: Optional[int]) -> str:
    """
    Форматировать длительность в читаемый вид.
    Например: 125 секунд -> "2:05"
    """
    if seconds is None:
        return "0:00"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_deleted_message(
    content_type: str,
    message_text: Optional[str],
    duration: Optional[int],
    extra_data: Optional[str],
    user_fullname_escaped: str,
    user_id: int,
    user_link: str,
    timestamp: str,
    is_outgoing: bool = False
) -> str:
    """
    Форматировать уведомление об удаленном сообщении.
    Выбирает правильный шаблон в зависимости от типа контента.
    """
    # Префикс для исходящих сообщений
    prefix = "[ВЫ] " if is_outgoing else ""
    
    base_params = {
        "user_fullname_escaped": user_fullname_escaped,
        "user_id": user_id,
        "user_link": user_link,
        "timestamp": timestamp
    }
    
    # Блок подписи (если есть текст)
    caption_block = ""
    if message_text:
        caption_block = lang.CAPTION_BLOCK.format(caption=message_text)
    
    duration_str = format_duration(duration)
    
    # Выбор шаблона по типу контента
    if content_type == "text":
        msg = lang.DELETED_MESSAGE_FORMAT.format(
            **base_params, 
            old_text=message_text or "[пусто]"
        )
    
    elif content_type == "photo":
        msg = lang.DELETED_PHOTO_FORMAT.format(
            **base_params, 
            caption_block=caption_block
        )
    
    elif content_type == "video":
        msg = lang.DELETED_VIDEO_FORMAT.format(
            **base_params, 
            duration=duration_str,
            caption_block=caption_block
        )
    
    elif content_type == "video_note":
        msg = lang.DELETED_VIDEO_NOTE_FORMAT.format(
            **base_params, 
            duration=duration_str
        )
    
    elif content_type == "voice":
        msg = lang.DELETED_VOICE_FORMAT.format(
            **base_params, 
            duration=duration_str,
            caption_block=caption_block
        )
    
    elif content_type == "audio":
        performer = ""
        title = extra_data or "Unknown"
        if extra_data and " - " in extra_data:
            parts = extra_data.split(" - ", 1)
            performer = parts[0]
            title = parts[1]
            
        msg = lang.DELETED_AUDIO_FORMAT.format(
            **base_params, 
            duration=duration_str,
            performer=escape(performer),
            title=escape(title),
            caption_block=caption_block
        )
    
    elif content_type == "document":
        file_name_escaped = escape(extra_data or "Файл")
        msg = lang.DELETED_DOCUMENT_FORMAT.format(
            **base_params, 
            file_name=file_name_escaped,
            caption_block=caption_block
        )
    
    elif content_type == "sticker":
        msg = lang.DELETED_STICKER_FORMAT.format(
            **base_params,
            emoji=message_text or ""
        )
    
    elif content_type == "animation":
        msg = lang.DELETED_ANIMATION_FORMAT.format(
            **base_params, 
            duration=duration_str,
            caption_block=caption_block
        )
    
    elif content_type == "contact":
        msg = lang.DELETED_CONTACT_FORMAT.format(
            **base_params, 
            contact_info=extra_data or ""
        )
    
    elif content_type == "location":
        msg = lang.DELETED_LOCATION_FORMAT.format(
            **base_params, 
            coordinates=extra_data or ""
        )
    
    elif content_type == "venue":
        msg = lang.DELETED_VENUE_FORMAT.format(
            **base_params, 
            venue_info=extra_data or ""
        )
    
    elif content_type == "poll":
        msg = lang.DELETED_POLL_FORMAT.format(
            **base_params, 
            question=message_text or ""
        )
    
    elif content_type == "dice":
        msg = lang.DELETED_DICE_FORMAT.format(
            **base_params, 
            dice_emoji=message_text or "Кубик",
            dice_value=extra_data or "?"
        )
    
    elif content_type == "game":
        msg = lang.DELETED_GAME_FORMAT.format(
            **base_params, 
            game_title=message_text or "Игра"
        )
    
    else:
        type_name = lang.CONTENT_TYPE_NAMES.get(content_type, content_type)
        msg = lang.DELETED_MESSAGE_FORMAT.format(
            **base_params, 
            old_text=f"[{type_name}]"
        )
    
    # Добавляем префикс для исходящих
    if is_outgoing and prefix:
        msg = msg.replace("[УДАЛЕНО]", f"[УДАЛЕНО] {prefix}", 1)
    
    return msg
