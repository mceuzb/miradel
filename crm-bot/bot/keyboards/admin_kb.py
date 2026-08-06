from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.database.models import ContestStatus, ContestType, GroupEnrollmentStatus
from bot.services.module_service import MODULE_KEYS

CONTEST_TYPE_LABELS = {
    ContestType.REFERRAL: "🏆 Referal asosida (eng ko'p taklif)",
    ContestType.RANDOM: "🎲 Random konkurs (tasodifiy tanlov)",
}

ENROLLMENT_STATUS_LABELS = {
    GroupEnrollmentStatus.OPEN: "🟢 Qabul ochiq",
    GroupEnrollmentStatus.FILLING: "🟡 To'lmoqda",
    GroupEnrollmentStatus.FEW_SPOTS: "🔴 Joylar kam qolmoqda",
    GroupEnrollmentStatus.CLOSED: "⚫️ Yopiq (ommaga ko'rinmaydi)",
}


def group_status_select_kb(callback_prefix: str) -> InlineKeyboardMarkup:
    """Guruh yaratishda yoki statusni o'zgartirishda ko'rsatiladigan tanlov
    tugmalari. callback_prefix masalan: 'set_group_status' yoki
    'edit_group_status:<group_id>'."""
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"{callback_prefix}:{status.value}")]
        for status, label in ENROLLMENT_STATUS_LABELS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def groups_list_kb(groups) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"✏️ {g.name} — {ENROLLMENT_STATUS_LABELS[g.enrollment_status]}",
            callback_data=f"edit_group_status:{g.id}",
        )]
        for g in groups
    ]
    rows.append([InlineKeyboardButton(text="➕ Yangi guruh qo'shish", callback_data="new_group")])
    rows.append([InlineKeyboardButton(
        text="📢 Eski o'quvchilarga kurs so'rash", callback_data="broadcast_course_selection",
    )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def contest_type_select_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"contest_type:{ctype.value}")]
        for ctype, label in CONTEST_TYPE_LABELS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def contests_kb(contests) -> InlineKeyboardMarkup:
    rows = []
    for c in contests:
        type_icon = "🎲" if c.contest_type == ContestType.RANDOM else "🏆"
        if c.status == ContestStatus.ACTIVE:
            if c.contest_type == ContestType.RANDOM:
                rows.append([
                    InlineKeyboardButton(text=f"{type_icon} #{c.id} ishtirokchilar", callback_data=f"contest_participants_count:{c.id}"),
                    InlineKeyboardButton(text=f"🏁 #{c.id} g'oliblarni e'lon qilish", callback_data=f"finish_random_contest:{c.id}"),
                ])
            else:
                rows.append([
                    InlineKeyboardButton(text=f"{type_icon} #{c.id} reyting", callback_data=f"contest_rating:{c.id}"),
                    InlineKeyboardButton(text=f"🏁 #{c.id} yakunlash", callback_data=f"finish_contest:{c.id}"),
                ])
            rows.append([InlineKeyboardButton(text=f"📥 #{c.id} Excel yuklab olish", callback_data=f"contest_export:{c.id}")])
        elif c.status == ContestStatus.FINISHED:
            rows.append([InlineKeyboardButton(text=f"{type_icon} #{c.id} g'oliblar", callback_data=f"contest_results:{c.id}")])
            rows.append([InlineKeyboardButton(text=f"📥 #{c.id} Excel yuklab olish", callback_data=f"contest_export:{c.id}")])
    rows.append([InlineKeyboardButton(text="➕ Yangi konkurs", callback_data="new_contest")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
