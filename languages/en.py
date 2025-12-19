# Message formats for English language

EDITED_MESSAGE_FORMAT = (
    '<b>[EDITED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Was:</b>\n'
    '<blockquote><code>{old_text}</code></blockquote>\n'
    '<b>Now:</b>\n'
    '<blockquote><code>{new_text}</code></blockquote>'
)

DELETED_MESSAGE_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted:</b>\n'
    '<blockquote><code>{old_text}</code></blockquote>'
)

NEW_USER_MESSAGE_FORMAT = (
    '<b>[NEW CLIENT] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ]</b>\n\n'
    '<b>ID: </b><code>{user_id}</code>'
)

# Media formats with optional caption
DELETED_PHOTO_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Photo</b>{caption_block}'
)

DELETED_VIDEO_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Video</b>\n'
    'Duration: {duration}{caption_block}'
)

DELETED_VIDEO_NOTE_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Video Note</b>\n'
    'Duration: {duration}'
)

DELETED_VOICE_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Voice Message</b>\n'
    'Duration: {duration}'
)

DELETED_AUDIO_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Audio</b>\n'
    'Duration: {duration}{caption_block}'
)

DELETED_DOCUMENT_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Document</b>{caption_block}'
)

DELETED_STICKER_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Sticker</b>'
)

DELETED_ANIMATION_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: GIF</b>\n'
    'Duration: {duration}{caption_block}'
)

DELETED_CONTACT_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Contact</b>\n'
    '<blockquote>{contact_info}</blockquote>'
)

DELETED_LOCATION_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Location</b>\n'
    'Coordinates: <code>{coordinates}</code>'
)

DELETED_POLL_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Poll</b>\n'
    'Question: {question}'
)

DELETED_VENUE_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Venue</b>\n'
    '{venue_info}'
)

DELETED_DICE_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: {dice_emoji}</b>\n'
    'Value: {dice_value}'
)

DELETED_GAME_FORMAT = (
    '<b>[DELETED] [ <a href="tg://user?id={user_id}">{user_fullname_escaped}</a> ] '
    '<code>{user_id}</code></b>\n'
    'Message from {timestamp}\n\n'
    '<b>Deleted: Game</b>\n'
    '{game_title}'
)

OWNER_CONNECTED_FORMAT = (
    '<b>[CONNECTED]</b>\n\n'
    'Bot successfully connected to your Telegram Business account.\n'
    'You will now receive notifications about edited and deleted messages from clients.'
)

OWNER_DISCONNECTED_FORMAT = (
    '<b>[DISCONNECTED]</b>\n\n'
    'Bot disconnected from your Telegram Business account.'
)

# Content type names for unknown types
CONTENT_TYPE_NAMES = {
    'text': 'Text',
    'photo': 'Photo',
    'video': 'Video',
    'video_note': 'Video Note',
    'voice': 'Voice Message',
    'audio': 'Audio',
    'document': 'Document',
    'sticker': 'Sticker',
    'animation': 'GIF',
    'contact': 'Contact',
    'location': 'Location',
    'poll': 'Poll',
    'venue': 'Venue',
    'dice': 'Dice',
    'game': 'Game',
}

# Caption block template
CAPTION_BLOCK = '\n<b>Caption:</b>\n<blockquote><code>{caption}</code></blockquote>'
