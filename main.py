"""
All-Seeing Bot - Telegram Business Message Tracker
Tracks edited and deleted messages from clients and owners.
Supports multiple owners and various media types.
"""

import configparser
import json
import importlib
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from html import escape

import pytz
from aiogram import Router, Bot, Dispatcher, F, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command

from database import OwnersDB, UsersDB, MessagesDB

# Load configuration
config = configparser.ConfigParser()
config.read("config.ini")

TOKEN = config["telegram"]["token"].strip('"')
TIMEZONE_NAME = config["timezone"]["name"].strip('"')
LANGUAGE = config["settings"]["language"].strip('"')

timezone_local = pytz.timezone(TIMEZONE_NAME)

# Load language module
try:
    lang = importlib.import_module(f"languages.{LANGUAGE}")
except ImportError:
    raise ImportError(f"Language module for '{LANGUAGE}' not found.")

router = Router(name=__name__)
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in human-readable format."""
    if seconds is None:
        return "0:00"
    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def get_content_type(message: types.Message) -> dict:
    """
    Determine message content type and extract all metadata.
    Returns dict with: content_type, text, duration, file_size, extra_data
    """
    result = {
        "content_type": "unknown",
        "text": None,
        "duration": None,
        "file_size": None,
        "extra_data": None
    }
    
    meta = {}
    
    if message.text:
        result["content_type"] = "text"
        result["text"] = message.text
    
    elif message.photo:
        result["content_type"] = "photo"
        result["text"] = message.caption
        largest = message.photo[-1]
        result["file_size"] = largest.file_size
        meta["file_id"] = largest.file_id
    
    elif message.video:
        result["content_type"] = "video"
        result["text"] = message.caption
        result["duration"] = message.video.duration
        result["file_size"] = message.video.file_size
        meta["file_id"] = message.video.file_id
    
    elif message.video_note:
        result["content_type"] = "video_note"
        result["duration"] = message.video_note.duration
        result["file_size"] = message.video_note.file_size
        meta["file_id"] = message.video_note.file_id
    
    elif message.voice:
        result["content_type"] = "voice"
        result["duration"] = message.voice.duration
        result["file_size"] = message.voice.file_size
        meta["file_id"] = message.voice.file_id
    
    elif message.audio:
        result["content_type"] = "audio"
        result["text"] = message.caption
        result["duration"] = message.audio.duration
        result["file_size"] = message.audio.file_size
        meta["file_id"] = message.audio.file_id
        if message.audio.title or message.audio.performer:
            meta["info"] = f"{message.audio.performer or ''} - {message.audio.title or ''}".strip(" -")
    
    elif message.document:
        result["content_type"] = "document"
        result["text"] = message.caption
        result["file_size"] = message.document.file_size
        meta["file_id"] = message.document.file_id
        if message.document.file_name:
            meta["info"] = message.document.file_name
    
    elif message.sticker:
        result["content_type"] = "sticker"
        result["text"] = message.sticker.emoji
        result["file_size"] = message.sticker.file_size
        meta["file_id"] = message.sticker.file_id
    
    elif message.animation:
        result["content_type"] = "animation"
        result["text"] = message.caption
        result["duration"] = message.animation.duration
        result["file_size"] = message.animation.file_size
        meta["file_id"] = message.animation.file_id
    
    elif message.contact:
        result["content_type"] = "contact"
        contact = message.contact
        meta["info"] = f"{contact.first_name} {contact.last_name or ''}: {contact.phone_number}".strip()
    
    elif message.location:
        result["content_type"] = "location"
        loc = message.location
        meta["info"] = f"{loc.latitude}, {loc.longitude}"
    
    elif message.venue:
        result["content_type"] = "venue"
        venue = message.venue
        meta["info"] = f"{venue.title}\n{venue.address}"
    
    elif message.poll:
        result["content_type"] = "poll"
        result["text"] = message.poll.question
        if message.poll.options:
            meta["options"] = [o.text for o in message.poll.options]
    
    elif message.dice:
        result["content_type"] = "dice"
        result["text"] = message.dice.emoji
        meta["value"] = str(message.dice.value)
    
    elif message.game:
        result["content_type"] = "game"
        result["text"] = message.game.title
        meta["description"] = message.game.description
    
    # Handle service messages (calls, video chats)
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
            # Fallback for other content types
            result["content_type"] = message.content_type
            result["text"] = message.text or message.caption
            
    if meta:
        result["extra_data"] = json.dumps(meta)
        
    return result


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
    """Format notification message for deleted content based on type."""
    # Add prefix for outgoing messages
    prefix = "[ВЫ] " if is_outgoing else ""
    
    base_params = {
        "user_fullname_escaped": user_fullname_escaped,
        "user_id": user_id,
        "user_link": user_link,
        "timestamp": timestamp
    }
    
    # Format caption block if text exists
    caption_block = ""
    if message_text:
        caption_block = lang.CAPTION_BLOCK.format(caption=message_text)
    
    duration_str = format_duration(duration)
    
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
        # Parse performer and title from extra_data if possible
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
    
    # Insert prefix after first tag for outgoing messages
    if is_outgoing and prefix:
        msg = msg.replace("[УДАЛЕНО]", f"[УДАЛЕНО] {prefix}", 1)
    
    return msg


async def send_notification(bot: Bot, owner_id: int, message: str) -> bool:
    """Send notification to owner. Returns success status."""
    try:
        await bot.send_message(owner_id, message, parse_mode='html')
        return True
    except Exception as e:
        logger.error(f"Failed to send notification to {owner_id}: {e}")
        return False


@router.business_connection()
async def handle_business_connection(event: types.BusinessConnection):
    """Handle when a user connects/disconnects the bot to their Telegram Business."""
    user_id = event.user.id
    user_fullname = event.user.full_name
    connection_id = event.id
    
    if event.is_enabled:
        OwnersDB.add(
            user_id=user_id,
            business_connection_id=connection_id,
            user_fullname=user_fullname,
            username=event.user.username
        )
        logger.info(f"Owner connected: {user_fullname} ({user_id})")
        
        try:
            await event.bot.send_message(
                user_id,
                lang.OWNER_CONNECTED_FORMAT.format(user_fullname=user_fullname),
                parse_mode='html'
            )
        except Exception as e:
            logger.error(f"Failed to send connection confirmation to {user_id}: {e}")
    else:
        OwnersDB.delete(user_id=user_id)
        logger.info(f"Owner disconnected: {user_fullname} ({user_id})")
        
        try:
            await event.bot.send_message(
                user_id,
                lang.OWNER_DISCONNECTED_FORMAT,
                parse_mode='html'
            )
        except Exception as e:
            logger.error(f"Failed to send disconnection notice to {user_id}: {e}")


@router.message(Command(commands=["start"]))
async def start_command(message: types.Message):
    """Handle /start command with status check."""
    user_id = message.from_user.id
    
    # Check if user is already an owner
    owner = OwnersDB.get_by_user_id(user_id)
    
    if owner:
        # User is connected
        msg = lang.START_MESSAGE_CONNECTED
    else:
        # User not found (likely not connected or just Premium user without business setup)
        premium_status = lang.STATUS_UNKNOWN
        bot_status = lang.STATUS_NOT_CONNECTED
        
        msg = lang.START_MESSAGE_NOT_CONNECTED.format(
            premium_status=premium_status,
            bot_status=bot_status
        )
    
    await message.answer(msg, parse_mode='html')

async def on_startup(bot: Bot):
    await bot.set_my_commands([
        types.BotCommand(command="start", description="Перезапуск / Статус"),
        types.BotCommand(command="settings", description="Настройки"),
    ])


@router.message(Command(commands=["settings"]))
async def settings_command(message: types.Message):
    """Handle /settings command."""
    user_id = message.from_user.id
    
    # Check if user is an owner
    owner = OwnersDB.get_by_user_id(user_id)
    if not owner:
        await message.answer(lang.START_MESSAGE_NOT_CONNECTED, parse_mode='html')
        return

    # Get current setting
    notify_on_edit = owner.get("notify_on_edit", False)
    
    status_text = lang.SETTINGS_ENABLED if notify_on_edit else lang.SETTINGS_DISABLED
    button_text = f"{lang.SETTINGS_NOTIFY_EDIT_BTN}: {status_text}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, callback_data="settings_toggle_edit_notify")]
    ])
    
    await message.answer(lang.SETTINGS_HEADER, reply_markup=keyboard, parse_mode='html')


@router.callback_query(F.data == "settings_toggle_edit_notify")
async def settings_toggle_callback(callback: CallbackQuery):
    """Handle settings toggle callback."""
    user_id = callback.from_user.id
    
    owner = OwnersDB.get_by_user_id(user_id)
    if not owner:
        await callback.answer(lang.STATUS_NOT_CONNECTED, show_alert=True)
        return
        
    current_status = owner.get("notify_on_edit", False)
    new_status = not current_status
    
    # Update DB
    if OwnersDB.update_settings(user_id, new_status):
        # Update message
        status_text = lang.SETTINGS_ENABLED if new_status else lang.SETTINGS_DISABLED
        button_text = f"{lang.SETTINGS_NOTIFY_EDIT_BTN}: {status_text}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=button_text, callback_data="settings_toggle_edit_notify")]
        ])
        
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer(lang.SETTINGS_UPDATED_NOTIFICATION)
    else:
        await callback.answer("Error updating settings", show_alert=True)




@router.edited_business_message()
async def handle_edited_business_message(message: types.Message):
    """Handle when a message is edited (both incoming and outgoing)."""
    connection_id = message.business_connection_id
    owner = OwnersDB.get_by_connection_id(connection_id)
    if not owner:
        logger.warning(f"Owner not found for connection: {connection_id}")
        return
    
    owner_id = owner["user_id"]
    chat_id = message.chat.id
    is_outgoing = message.from_user.id != message.chat.id
    
    # Get stored message
    stored = MessagesDB.get(owner_id=owner_id, chat_id=chat_id, message_id=message.message_id)
    if not stored:
        return
        
    # Check settings for outgoing messages (my edits)
    # Incoming messages (from clients) are ALWAYS notified
    if is_outgoing:
        notify_on_edit = owner.get("notify_on_edit", False)
        if not notify_on_edit:
            return

    
    # Determine new text based on message type
    new_text = message.text or message.caption
    
    # Skip if text hasn't changed (e.g. media edited but caption same)
    if stored["message_text"] == new_text:
        return
        
    old_text = stored["message_text"] or "[пусто]"
    new_text = new_text or "[пусто]"
    
    # Format timestamp
    message_timestamp = datetime.fromisoformat(stored["timestamp"].replace('Z', '+00:00'))
    message_timestamp_local = message_timestamp.astimezone(timezone_local)
    timestamp_formatted = message_timestamp_local.strftime('%d/%m/%y %H:%M')
    
    # Determine user info based on direction
    # Determine user info and link
    username = None
    if is_outgoing:
        user_fullname_escaped = "Вы"
        user_id = chat_id
        # Try to find client username in DB
        client_user = UsersDB.get(user_id=chat_id, owner_id=owner_id)
        if client_user:
            username = client_user.get("username")
    else:
        user_fullname_escaped = escape(message.from_user.full_name)
        user_id = message.from_user.id
        username = message.from_user.username
        
    # Construct link
    if username:
        user_link = f"https://t.me/{username}"
    else:
        user_link = f"tg://user?id={user_id}"
    
    msg = lang.EDITED_MESSAGE_FORMAT.format(
        user_fullname_escaped=user_fullname_escaped,
        user_link=user_link,
        timestamp=timestamp_formatted,
        old_text=old_text,
        new_text=new_text
    )
    
    if is_outgoing:
        msg = msg.replace("ИЗМЕНЕНО", "ИЗМЕНЕНО (ВЫ)", 1)
    
    await send_notification(message.bot, owner_id, msg)
    
    # Update stored message
    # Run DB write in background thread to avoid blocking
    asyncio.create_task(asyncio.to_thread(
        MessagesDB.update,
        owner_id=owner_id,
        chat_id=chat_id,
        message_id=message.message_id,
        message_text=new_text
    ))


@router.deleted_business_messages()
async def handle_deleted_business_messages(event: types.BusinessMessagesDeleted):
    """Handle when messages are deleted (both incoming and outgoing)."""
    chat = event.chat
    chat_id = chat.id
    user_fullname = chat.full_name or chat.first_name or "Unknown"
    user_fullname_escaped = escape(user_fullname)
    
    connection_id = event.business_connection_id
    owner = OwnersDB.get_by_connection_id(connection_id)
    if not owner:
        logger.warning(f"Owner not found for connection: {connection_id}")
        return
    
    owner_id = owner["user_id"]
    
    for msg_id in event.message_ids:
        stored = MessagesDB.get(owner_id=owner_id, chat_id=chat_id, message_id=msg_id)
        if not stored:
            continue
        
        is_outgoing = stored.get("is_outgoing", False)
        
        # Check settings for outgoing messages (my deletions)
        if is_outgoing:
            notify_on_edit = owner.get("notify_on_edit", False)
            if not notify_on_edit:
                # Remove from DB anyway to keep it clean, but don't notify
                MessagesDB.delete(owner_id=owner_id, chat_id=chat_id, message_id=msg_id)
                continue
        
        # Format timestamp
        message_timestamp = datetime.fromisoformat(stored["timestamp"].replace('Z', '+00:00'))
        message_timestamp_local = message_timestamp.astimezone(timezone_local)
        timestamp_formatted = message_timestamp_local.strftime('%d/%m/%y %H:%M')
        
        # Parse extra_data (handle both legacy string and new JSON)
        extra_data_raw = stored.get("extra_data")
        meta = {}
        file_id = None
        extra_data_str = extra_data_raw
        
        if extra_data_raw and extra_data_raw.startswith('{'):
            try:
                meta = json.loads(extra_data_raw)
                file_id = meta.get("file_id")
                # Extract info string for format function
                extra_data_str = meta.get("info") or meta.get("value") or meta.get("description")
            except json.JSONDecodeError:
                pass # Treat as legacy string
        
        # Determine user info and link for deletion
        # Note: stored message has info about sender
        sender_username = stored.get("sender_username")
        stored_user_id = stored.get("sender_id")
        
        # Override if outgoing
        if is_outgoing:
            # For outgoing, sender is owner (us), but checking if we want to link to client or us
            # In edit logic we linked to "Вы" (us) but effectively used client info if possible?
            # Actually in edit logic: 
            # if outgoing: user_fullname="Вы", user_id=chat_id (client ID).
            # Let's align with edit logic
            
            # Try to find client username in DB (chat_id is client)
            client_user = UsersDB.get(user_id=chat_id, owner_id=owner_id)
            if client_user and client_user.get("username"):
                sender_username = client_user.get("username")
            
            # Use client ID for link generation if outgoing (to link to chat with them)
            link_user_id = chat_id
        else:
            link_user_id = stored_user_id
            
        # Construct link
        if sender_username:
            user_link = f"https://t.me/{sender_username}"
        else:
            user_link = f"tg://user?id={link_user_id}"

        # Format text message (used as caption for media or fallback)
        msg = format_deleted_message(
            content_type=stored["content_type"],
            message_text=stored["message_text"],
            duration=stored["media_duration"],
            extra_data=extra_data_str,
            user_fullname_escaped="Вы" if is_outgoing else user_fullname_escaped,
            user_id=chat_id, # Keep chat_id as user_id param for consistency/legacy use if any
            user_link=user_link,
            timestamp=timestamp_formatted,
            is_outgoing=is_outgoing
        )
        
        # Try to send actual media if available
        sent_media = False
        if file_id:
            try:
                content_type = stored["content_type"]
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
                
                # Types without caption support: send text then media
                elif content_type == "sticker":
                    await send_notification(event.bot, owner_id, msg)
                    await event.bot.send_sticker(owner_id, file_id)
                    sent_media = True
                elif content_type == "video_note":
                    await send_notification(event.bot, owner_id, msg)
                    await event.bot.send_video_note(owner_id, file_id)
                    sent_media = True
                    
            except Exception as e:
                logger.warning(f"Failed to resend media ({stored['content_type']}): {e}")
                # Fallback to text notification will happen below
        
        if not sent_media:
            await send_notification(event.bot, owner_id, msg)
            
        MessagesDB.delete(owner_id=owner_id, chat_id=chat_id, message_id=msg_id)


@router.business_message()
async def handle_business_message(message: types.Message):
    """Handle all business messages (both incoming and outgoing)."""
    connection_id = message.business_connection_id
    owner = OwnersDB.get_by_connection_id(connection_id)
    if not owner:
        logger.warning(f"Owner not found for connection: {connection_id}")
        return
    
    owner_id = owner["user_id"]
    chat_id = message.chat.id
    
    # Determine if this is an outgoing message (owner sending to client)
    is_outgoing = message.from_user.id != message.chat.id
    
    # For incoming messages, track the user
    if not is_outgoing:
        user_id = message.from_user.id
        user_fullname = message.from_user.full_name
        user_fullname_escaped = escape(user_fullname)
        
        # Check if new user for this owner
        user_record = UsersDB.get(user_id=user_id, owner_id=owner_id)
        if not user_record:
            UsersDB.add(user_id=user_id, owner_id=owner_id, user_fullname=user_fullname, username=message.from_user.username)
            msg = lang.NEW_USER_MESSAGE_FORMAT.format(
                user_fullname_escaped=user_fullname_escaped,
                user_id=user_id
            )
            await send_notification(message.bot, owner_id, msg)
    
    # Extract content info
    content_info = get_content_type(message)
    
    # Store message
    message_datetime_utc = message.date.replace(tzinfo=timezone.utc)
    timestamp_iso = message_datetime_utc.isoformat()
    
    # Run DB write in background thread to avoid blocking
    asyncio.create_task(asyncio.to_thread(
        MessagesDB.add,
        owner_id=owner_id,
        chat_id=chat_id,
        message_id=message.message_id,
        timestamp=timestamp_iso,
        sender_id=message.from_user.id,
        sender_fullname=message.from_user.full_name,
        sender_username=message.from_user.username,
        is_outgoing=is_outgoing,
        content_type=content_info["content_type"],
        message_text=content_info["text"],
        media_duration=content_info["duration"],
        media_file_size=content_info["file_size"],
        extra_data=content_info["extra_data"]
    ))


async def cleanup_old_messages():
    """Periodic task to clean up messages older than 30 days."""
    while True:
        now_local = datetime.now(timezone_local)
        next_run = now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        sleep_seconds = (next_run - now_local).total_seconds()
        await asyncio.sleep(sleep_seconds)
        
        cutoff_datetime = datetime.now(timezone.utc) - timedelta(days=30)
        cutoff_timestamp = cutoff_datetime.isoformat()
        deleted_count = MessagesDB.delete_old_messages(cutoff_timestamp)
        logger.info(f"Cleanup: deleted {deleted_count} old messages")


async def main() -> None:
    """Main entry point."""
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)
    
    # Start cleanup task
    asyncio.create_task(cleanup_old_messages())
    
    logger.info("Bot starting...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())