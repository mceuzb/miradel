from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database.models import Group
from bot.keyboards.admin_kb import ENROLLMENT_STATUS_LABELS


def course_select_kb(groups: list[Group], callback_prefix: str, include_skip: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{ENROLLMENT_STATUS_LABELS[g.enrollment_status]} {g.name}",
            callback_data=f"{callback_prefix}:{g.id}",
        )]
        for g in groups
    ]
    if include_skip:
        rows.append([InlineKeyboardButton(text="⏭ Hozircha tanlamayman", callback_data=f"{callback_prefix}:skip")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
