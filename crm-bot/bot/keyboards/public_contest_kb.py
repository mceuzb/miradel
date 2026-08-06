from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database.models import Contest, ContestType


def public_contests_kb(contests: list[Contest]) -> InlineKeyboardMarkup:
    rows = []
    for c in contests:
        if c.contest_type == ContestType.RANDOM:
            text = f"🎲 #{c.id} '{c.title}' - Qatnashish"
            callback_data = f"join_random:{c.id}"
        else:
            text = f"🔗 #{c.id} '{c.title}' - Havola olish"
            callback_data = "get_referral_link"
        rows.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    return InlineKeyboardMarkup(inline_keyboard=rows)
