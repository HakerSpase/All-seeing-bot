"""
Обработчики команд бота.
/start, /settings, /backup и настройки через inline-кнопки.
"""
import asyncio
from datetime import datetime

from aiogram import Router, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, WebAppInfo
from aiogram.filters import Command
from aiogram import F
from typing import Optional

import csv
import io
import os
from config import lang, ADMIN_ID
from database import OwnersDB, BackupsDB, MessagesDB, UsersDB
from storage import StorageManager

router = Router(name="commands")

# Ссылка на StorageManager (устанавливается из main.py)
_storage_mgr: Optional[StorageManager] = None


def set_storage_manager(manager: StorageManager):
    """Установить менеджер хранилища для команды /backup."""
    global _storage_mgr
    _storage_mgr = manager


@router.message(Command(commands=["start"]))
async def start_command(message: types.Message):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    
    # Проверяем, подключен ли пользователь
    owner = await asyncio.to_thread(OwnersDB.get_by_user_id, user_id)
    
    if owner:
        msg = lang.START_MESSAGE_CONNECTED
    else:
        # Проверяем Premium
        is_premium = bool(message.from_user.is_premium)
        premium_status = lang.STATUS_CONNECTED if is_premium else lang.STATUS_NOT_CONNECTED
        
        bot_status = lang.STATUS_NOT_CONNECTED
        
        msg = lang.START_MESSAGE_NOT_CONNECTED.format(
            premium_status=premium_status,
            bot_status=bot_status
        )
    
    await message.answer(msg, parse_mode='html')


@router.message(Command(commands=["settings"]))
async def settings_command(message: types.Message):
    """Обработчик команды /settings."""
    user_id = message.from_user.id
    
    owner = await asyncio.to_thread(OwnersDB.get_by_user_id, user_id)
    if not owner:
        msg = lang.START_MESSAGE_NOT_CONNECTED.format(
            premium_status=lang.STATUS_UNKNOWN,
            bot_status=lang.STATUS_NOT_CONNECTED
        )
        await message.answer(msg, parse_mode='html')
        return

    # Получаем текущую настройку
    notify_on_edit = owner.get("notify_on_edit", False)
    
    status_text = lang.SETTINGS_ENABLED if notify_on_edit else lang.SETTINGS_DISABLED
    button_text = f"{lang.SETTINGS_NOTIFY_EDIT_BTN}: {status_text}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=button_text, callback_data="settings_toggle_edit_notify")]
    ])
    
    await message.answer(lang.SETTINGS_HEADER, reply_markup=keyboard, parse_mode='html')


@router.message(Command(commands=["backup"]))
async def backup_command(message: types.Message):
    """
    Команда принудительного бэкапа (только для админа).
    Переносит все данные из Supabase в Google Sheets.
    """
    user_id = message.from_user.id
    
    # Проверяем, что пользователь — админ
    if user_id != ADMIN_ID:
        await message.answer("⛔ Эта команда доступна только администратору.", parse_mode='html')
        return
    
    # Получаем статистику (асинхронно чтобы не блокировать)
    stats = await asyncio.to_thread(BackupsDB.get_stats)
    last_time = stats.get("last_backup_time", "никогда")
    if last_time and last_time != "никогда":
        # Форматируем время
        try:
            dt = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
            last_time = dt.strftime('%d.%m.%Y %H:%M')
        except:
            pass
    
    # Получаем количество сообщений для переноса (асинхронно)
    pending_count = await asyncio.to_thread(MessagesDB.count)
    
    msg = (
        "<b>🔄 Ручной бэкап</b>\n\n"
        f"Последний бэкап: <code>{last_time}</code>\n"
        f"Всего бэкапов: {stats.get('success_backups', 0)}\n"
        f"Всего перенесено: {stats.get('total_messages_transferred', 0)} сообщений\n\n"
        f"<b>Готово к переносу:</b> <code>{pending_count}</code> сообщений\n\n"
        "Выполнить бэкап сейчас?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, выполнить", callback_data="backup_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="backup_cancel")
        ]
    ])
    
    await message.answer(msg, reply_markup=keyboard, parse_mode='html')


@router.callback_query(F.data == "backup_confirm")
async def backup_confirm_callback(callback: CallbackQuery):
    """Подтверждение ручного бэкапа."""
    user_id = callback.from_user.id
    
    if user_id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    if not _storage_mgr:
        await callback.answer("Менеджер хранилища не инициализирован", show_alert=True)
        return
    
    # Обновляем сообщение
    await callback.message.edit_text(
        "<b>🔄 Бэкап выполняется...</b>\n\n"
        "Пожалуйста, подождите.",
        parse_mode='html'
    )
    
    # Выполняем бэкап
    result = await _storage_mgr.run_backup(is_manual=True)
    
    if result["success"]:
        msg = (
            "<b>✅ Бэкап завершён!</b>\n\n"
            f"Перенесено сообщений: <code>{result['count']}</code>\n"
            "Данные удалены из Supabase и записаны в Google Sheets."
        )
    else:
        msg = (
            "<b>❌ Ошибка бэкапа</b>\n\n"
            f"Причина: <code>{result.get('error', 'Неизвестная ошибка')}</code>"
        )
    
    await callback.message.edit_text(msg, parse_mode='html')
    await callback.answer()


@router.callback_query(F.data == "backup_cancel")
async def backup_cancel_callback(callback: CallbackQuery):
    """Отмена ручного бэкапа."""
    await callback.message.edit_text(
        "<b>❌ Бэкап отменён</b>",
        parse_mode='html'
    )
    await callback.answer()


@router.callback_query(F.data == "settings_toggle_edit_notify")
async def settings_toggle_callback(callback: CallbackQuery):
    """Переключение настройки уведомлений о своих редактированиях."""
    user_id = callback.from_user.id
    
    owner = await asyncio.to_thread(OwnersDB.get_by_user_id, user_id)
    if not owner:
        await callback.answer(lang.STATUS_NOT_CONNECTED, show_alert=True)
        return
        
    current_status = owner.get("notify_on_edit", False)
    new_status = not current_status
    
    if await asyncio.to_thread(OwnersDB.update_settings, user_id, new_status):
        status_text = lang.SETTINGS_ENABLED if new_status else lang.SETTINGS_DISABLED
        button_text = f"{lang.SETTINGS_NOTIFY_EDIT_BTN}: {status_text}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=button_text, callback_data="settings_toggle_edit_notify")]
        ])
        
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer(lang.SETTINGS_UPDATED_NOTIFICATION)
    else:
        await callback.answer("Ошибка обновления настроек", show_alert=True)


@router.message(Command(commands=["users"]))
async def users_export_command(message: types.Message):
    """
    Команда экспорта пользователей (только для админа).
    Генерирует CSV (Excel-совместимый) файл со списком владельцев и статистикой.
    """
    user_id = message.from_user.id
    
    # Проверка админа
    if user_id != ADMIN_ID:
        return
        
    status_msg = await message.answer("⏳ Собираю данные...", parse_mode='html')
    
    try:
        # Получаем всех владельцев
        owners = await asyncio.to_thread(OwnersDB.get_all)
        
        if not owners:
            await status_msg.edit_text("Пользователей не найдено.")
            return

        # Подготавливаем CSV в памяти
        output = io.StringIO()
        writer = csv.writer(output, dialect='excel', delimiter=';') # ; для Excel
        
        # Заголовки (без "Уведомления о правках")
        headers = [
            "User ID", 
            "Имя", 
            "Username", 
            "Дата подключения", 
            "ID подключения",
            "Сообщений в БД"
        ]
        writer.writerow(headers)
        
        # Заполняем данными
        for owner in owners:
            o_id = owner.get("user_id")
            
            # Считаем сообщения этого владельца в таблице messages
            msg_count = await asyncio.to_thread(MessagesDB.count_by_owner, o_id)
            
            # Форматируем дату
            reg_date = owner.get("created_at", "")
            try:
                dt = datetime.fromisoformat(reg_date.replace('Z', '+00:00'))
                reg_date = dt.strftime('%d.%m.%Y %H:%M')
            except:
                pass
            
            row = [
                str(o_id),
                owner.get("user_fullname", ""),
                f"@{owner.get('username', '')}" if owner.get('username') else "",
                reg_date,
                owner.get("business_connection_id", ""),
                str(msg_count)
            ]
            writer.writerow(row)
            
        # Отправляем файл
        output.seek(0)
        # Преобразуем в байты с BOM для корректного открытия в Excel (кириллица)
        bytes_io = io.BytesIO(output.getvalue().encode('utf-8-sig'))
        
        document = types.BufferedInputFile(
            file=bytes_io.read(),
            filename=f"users_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
        )
        
        await message.answer_document(
            document=document,
            caption=f"📊 <b>Экспорт пользователей</b>\nВсего владельцев: {len(owners)}",
            parse_mode='html'
        )
        await status_msg.delete()
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка экспорта: {e}")


@router.message(Command(commands=["panel"]))
async def panel_command(message: types.Message):
    """Открыть панель администратора (WebApp)."""
    user_id = message.from_user.id
    
    # Проверка: доступно владельцам или админу
    owner = await asyncio.to_thread(OwnersDB.get_by_user_id, user_id)
    if not owner and user_id != ADMIN_ID:
        await message.answer("⛔ Доступно только владельцам бизнес-подключения.")
        return

    # URL вашего веб-приложения (по умолчанию localhost для теста, если не задана переменная)
    # ПОЛЬЗОВАТЕЛЬ, ЗАМЕНИ ЭТО НА СВОЙ VERCEL URL В .env (WEBAPP_URL)
    web_app_url = os.getenv("WEBAPP_URL", "https://google.com") 
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Открыть Панель", web_app=WebAppInfo(url=web_app_url))]
    ])
    
    await message.answer(
        "<b>📱 Панель Администратора</b>\n\n"
        "Нажмите кнопку ниже, чтобы открыть панель управления.",
        reply_markup=keyboard,
        parse_mode='html'
    )


@router.message(Command(commands=["avatars"]))
async def avatars_command(message: types.Message):
    """
    Команда обновления аватарок всех пользователей И владельцев (только для админа).
    Загружает фото профилей из Telegram и сохраняет file_id в базу.
    """
    from database.supabase_client import supabase
    
    user_id = message.from_user.id
    
    if user_id != ADMIN_ID:
        await message.answer("⛔ Эта команда доступна только администратору.", parse_mode='html')
        return
    
    status_msg = await message.answer("🔄 <b>Обновление аватарок...</b>\n\nЗагружаю фото профилей...", parse_mode='html')
    
    try:
        updated_users = 0
        updated_owners = 0
        errors = 0
        
        # 1. Обновляем аватарки ВЛАДЕЛЬЦЕВ
        owners_response = supabase.table("owners").select("user_id, avatar_file_id").execute()
        owners = owners_response.data or []
        
        for owner in owners:
            uid = owner.get("user_id")
            if owner.get("avatar_file_id"):
                continue
            try:
                photos = await message.bot.get_user_profile_photos(uid, limit=1)
                if photos.total_count > 0:
                    avatar_file_id = photos.photos[0][0].file_id
                    supabase.table("owners").update({"avatar_file_id": avatar_file_id}).eq("user_id", uid).execute()
                    updated_owners += 1
            except:
                errors += 1
            await asyncio.sleep(0.1)
        
        # 2. Обновляем аватарки КЛИЕНТОВ
        users_response = supabase.table("users").select("user_id, owner_id, avatar_file_id").execute()
        users = users_response.data or []
        
        for user in users:
            uid = user.get("user_id")
            oid = user.get("owner_id")
            if user.get("avatar_file_id"):
                continue
            try:
                photos = await message.bot.get_user_profile_photos(uid, limit=1)
                if photos.total_count > 0:
                    avatar_file_id = photos.photos[0][0].file_id
                    await asyncio.to_thread(
                        UsersDB.update, 
                        user_id=uid, 
                        owner_id=oid, 
                        avatar_file_id=avatar_file_id
                    )
                    updated_users += 1
            except:
                errors += 1
            await asyncio.sleep(0.1)
        
        await status_msg.edit_text(
            f"<b>✅ Аватарки обновлены!</b>\n\n"
            f"Владельцев: <code>{updated_owners}</code>\n"
            f"Клиентов: <code>{updated_users}</code>\n"
            f"Ошибок: <code>{errors}</code>",
            parse_mode='html'
        )
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")

