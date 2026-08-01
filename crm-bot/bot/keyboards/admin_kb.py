from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database.models import ContestStatus
from bot.services.module_service import MODULE_KEYS


def approval_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ O'quvchi", callback_data=f"approve:student:{user_id}"),
            InlineKeyboardButton(text="✅ O'qituvchi", callback_data=f"approve:teacher:{user_id}"),
        ],
        [InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject:{user_id}")],
    ])


def modules_kb(modules) -> InlineKeyboardMarkup:
    rows = []
    for m in modules:
        status_icon = "🟢" if m.is_enabled else "🔴"
        title = MODULE_KEYS.get(m.module_key, m.module_key)
        rows.append([InlineKeyboardButton(
            text=f"{status_icon} {title}",
            callback_data=f"toggle_module:{m.module_key}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channels_kb(channels) -> InlineKeyboardMarkup:
    rows = []
    for ch in channels:
        status_icon = "🟢" if ch.is_active else "🔴"
        rows.append([
            InlineKeyboardButton(
                text=f"{status_icon} @{ch.channel_username}",
                callback_data=f"toggle_channel:{ch.id}",
            ),
            InlineKeyboardButton(text="🗑", callback_data=f"delete_channel:{ch.id}"),
        ])
    rows.append([InlineKeyboardButton(text="➕ Yangi kanal qo'shish", callback_data="add_channel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def contests_kb(contests) -> InlineKeyboardMarkup:
    rows = []
    for c in contests:
        if c.status == ContestStatus.ACTIVE:
            rows.append([
                InlineKeyboardButton(text=f"📊 #{c.id} reyting", callback_data=f"contest_rating:{c.id}"),
                InlineKeyboardButton(text=f"🏁 #{c.id} yakunlash", callback_data=f"finish_contest:{c.id}"),
            ])
            rows.append([InlineKeyboardButton(text=f"📥 #{c.id} Excel yuklab olish", callback_data=f"contest_export:{c.id}")])
        elif c.status == ContestStatus.FINISHED:
            rows.append([InlineKeyboardButton(text=f"🏆 #{c.id} g'oliblar", callback_data=f"contest_results:{c.id}")])
            rows.append([InlineKeyboardButton(text=f"📥 #{c.id} Excel yuklab olish", callback_data=f"contest_export:{c.id}")])
    rows.append([InlineKeyboardButton(text="➕ Yangi konkurs", callback_data="new_contest")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
