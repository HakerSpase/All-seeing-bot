"""
Русский языковой пакет для All-Seeing Bot.
Содержит все текстовые шаблоны для уведомлений.
"""

# ===== РЕДАКТИРОВАНИЕ =====
EDITED_MESSAGE_FORMAT = (
    '<b>ИЗМЕНЕНО</b>\n'
    '<a href="{user_link}">{user_fullname_escaped}</a> | {timestamp}\n\n'
    '<b>Было:</b>\n'
    '<blockquote>{old_text}</blockquote>\n\n'
    '<b>Стало:</b>\n'
    '<blockquote>{new_text}</blockquote>'
)

# ===== УДАЛЕНИЕ =====
DELETED_MESSAGE_FORMAT = (
    '<b>УДАЛЕНО</b>\n'
    '<a href="{user_link}">{user_fullname_escaped}</a> | {timestamp}\n\n'
    '<b>Сообщение:</b>\n'
    '<blockquote>{old_text}</blockquote>'
)

# ===== НОВЫЙ КЛИЕНТ =====
NEW_USER_MESSAGE_FORMAT = (
    '<b>[НОВЫЙ КЛИЕНТ] [ <a href="{user_link}">{user_fullname_escaped}</a> ]</b>\n\n'
    '<b>ID: </b><code>{user_id}</code>'
)

# ===== СТАРТОВЫЕ СООБЩЕНИЯ =====
START_MESSAGE_CONNECTED = (
    '<b>All-Seeing Bot</b>\n\n'
    '<blockquote><b>СТАТУС: АКТИВЕН</b>\n\n'
    '✅ Telegram Premium\n'
    '✅ Бот в Telegram Business</blockquote>\n\n'
    'Бот успешно работает и сохраняет историю сообщений в ваших чатах.'
)

START_MESSAGE_NOT_CONNECTED = (
    '<b>All-Seeing Bot</b>\n\n'
    'Этот бот отслеживает изменённые и удалённые сообщения в ваших чатах.\n\n'
    '<blockquote><b>СТАТУС ПОДКЛЮЧЕНИЯ</b>\n\n'
    '{premium_status} Telegram Premium\n'
    '{bot_status} Бот в Telegram Business</blockquote>\n\n'
    '<b>Как начать работу:</b>\n'
    '1. Настройки → Telegram Business → Чат-боты\n'
    '2. Добавить этого бота\n'
    '3. Выдать все разрешения'
)

# ===== ПОДКЛЮЧЕНИЕ/ОТКЛЮЧЕНИЕ =====
OWNER_CONNECTED_FORMAT = (
    '<b>[ПОДКЛЮЧЕНИЕ]</b>\n\n'
    'Бот успешно подключен к вашему Telegram Business аккаунту.\n'
    'Теперь вы будете получать уведомления об изменённых и удалённых сообщениях от клиентов.'
)

OWNER_DISCONNECTED_FORMAT = (
    '<b>[ОТКЛЮЧЕНИЕ]</b>\n\n'
    'Бот отключен от вашего Telegram Business аккаунта.'
)

# ===== СТАТУСЫ =====
STATUS_CONNECTED = "✅"
STATUS_NOT_CONNECTED = "❌"
STATUS_UNKNOWN = "❓"

# ===== УДАЛЕННЫЕ МЕДИА =====
DELETED_PHOTO_FORMAT = (
    '<b>[УДАЛЕНО] [ <a href="{user_link}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Сообщение от {timestamp}\n\n'
    '<b>Удалено: Фото</b>{caption_block}'
)

DELETED_VIDEO_FORMAT = (
    '<b>[УДАЛЕНО] [ <a href="{user_link}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Сообщение от {timestamp}\n\n'
    '<b>Удалено: Видео</b>\n'
    'Длительность: {duration}{caption_block}'
)

DELETED_VIDEO_NOTE_FORMAT = (
    '<b>УДАЛЕНО</b>\n'
    '<a href="{user_link}">{user_fullname_escaped}</a> | {timestamp}\n\n'
    '<b>Тип:</b> Видеокружок\n'
    'Длительность: {duration}\n\n'
    'Удаленный круг ниже 👇'
)

DELETED_VOICE_FORMAT = (
    '<b>УДАЛЕНО</b>\n'
    '<a href="{user_link}">{user_fullname_escaped}</a> | {timestamp}\n\n'
    '<b>Тип:</b> Голосовое\n'
    'Длительность: {duration}{caption_block}'
)

DELETED_AUDIO_FORMAT = (
    '<b>УДАЛЕНО</b>\n'
    '<a href="{user_link}">{user_fullname_escaped}</a> | {timestamp}\n\n'
    '<b>Тип:</b> Аудио\n'
    'Трек: {performer} - {title}\n'
    'Длительность: {duration}{caption_block}'
)

DELETED_DOCUMENT_FORMAT = (
    '<b>УДАЛЕНО</b>\n'
    '<a href="{user_link}">{user_fullname_escaped}</a> | {timestamp}\n\n'
    '<b>Тип:</b> Файл\n'
    'Имя: {file_name}{caption_block}'
)

DELETED_STICKER_FORMAT = (
    '<b>УДАЛЕНО</b>\n'
    '<a href="{user_link}">{user_fullname_escaped}</a> | {timestamp}\n\n'
    '<b>Тип:</b> Стикер\n'
    'Эмодзи: {emoji}\n\n'
    'Удаленный стикер ниже 👇'
)

DELETED_ANIMATION_FORMAT = (
    '<b>[УДАЛЕНО] [ <a href="{user_link}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Сообщение от {timestamp}\n\n'
    '<b>Удалено: GIF</b>\n'
    'Длительность: {duration}{caption_block}'
)

DELETED_CONTACT_FORMAT = (
    '<b>УДАЛЕНО</b>\n'
    '<a href="{user_link}">{user_fullname_escaped}</a> | {timestamp}\n\n'
    '<b>Тип:</b> Контакт\n'
    '{contact_info}'
)

DELETED_LOCATION_FORMAT = (
    '<b>[УДАЛЕНО] [ <a href="{user_link}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Сообщение от {timestamp}\n\n'
    '<b>Удалено: Геолокация</b>\n'
    'Координаты: <code>{coordinates}</code>'
)

DELETED_POLL_FORMAT = (
    '<b>[УДАЛЕНО] [ <a href="{user_link}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Сообщение от {timestamp}\n\n'
    '<b>Удалено: Опрос</b>\n'
    'Вопрос: {question}'
)

DELETED_VENUE_FORMAT = (
    '<b>[УДАЛЕНО] [ <a href="{user_link}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Сообщение от {timestamp}\n\n'
    '<b>Удалено: Место</b>\n'
    '{venue_info}'
)

DELETED_DICE_FORMAT = (
    '<b>[УДАЛЕНО] [ <a href="{user_link}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Сообщение от {timestamp}\n\n'
    '<b>Удалено: {dice_emoji}</b>\n'
    'Значение: {dice_value}'
)

DELETED_GAME_FORMAT = (
    '<b>[УДАЛЕНО] [ <a href="{user_link}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Сообщение от {timestamp}\n\n'
    '<b>Удалено: Игра</b>\n'
    '{game_title}'
)

# ===== НАЗВАНИЯ ТИПОВ КОНТЕНТА =====
CONTENT_TYPE_NAMES = {
    'text': 'Текст',
    'photo': 'Фото',
    'video': 'Видео',
    'video_note': 'Видеокружок',
    'voice': 'Голосовое сообщение',
    'audio': 'Аудио',
    'document': 'Документ',
    'sticker': 'Стикер',
    'animation': 'GIF',
    'contact': 'Контакт',
    'location': 'Геолокация',
    'poll': 'Опрос',
    'venue': 'Место',
    'dice': 'Кубик',
    'game': 'Игра',
}

# ===== БЛОК ПОДПИСИ =====
CAPTION_BLOCK = '\n<b>Подпись:</b>\n<blockquote><code>{caption}</code></blockquote>'

# ===== НАСТРОЙКИ =====
SETTINGS_HEADER = (
    '<b>⚙️ Настройки</b>\n\n'
    'Здесь вы можете настроить поведение бота.'
)

SETTINGS_NOTIFY_EDIT_BTN = "Мои изменения"
SETTINGS_ENABLED = "✅ Включено"
SETTINGS_DISABLED = "❌ Отключено"

SETTINGS_UPDATED_NOTIFICATION = "Настройки обновлены"
