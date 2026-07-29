from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

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
