from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove


def contact_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def guest_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📰 Yangiliklar"), KeyboardButton(text="📅 Kurslar jadvali")],
            [KeyboardButton(text="🎁 Konkurslar")],
            [KeyboardButton(text="📝 Ro'yxatdan o'tish")],
        ],
        resize_keyboard=True,
    )


def admin_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🆕 Yangi so'rovlar"), KeyboardButton(text="⚙️ Modullar")],
            [KeyboardButton(text="👥 Guruhlar"), KeyboardButton(text="📊 Hisobotlar")],
            [KeyboardButton(text="📢 Majburiy kanallar")],
        ],
        resize_keyboard=True,
    )


def teacher_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Guruhlarim"), KeyboardButton(text="✅ Davomat")],
            [KeyboardButton(text="📝 Vazifa berish"), KeyboardButton(text="📥 Topshiriqlar")],
        ],
        resize_keyboard=True,
    )


def student_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Kabinetim"), KeyboardButton(text="📝 Vazifalarim")],
            [KeyboardButton(text="📅 Dars jadvali"), KeyboardButton(text="📈 Davomatim")],
        ],
        resize_keyboard=True,
    )


def menu_for_role(role) -> ReplyKeyboardMarkup:
    from bot.database.models import UserRole
    mapping = {
        UserRole.ADMIN: admin_menu_kb,
        UserRole.TEACHER: teacher_menu_kb,
        UserRole.STUDENT: student_menu_kb,
    }
    return mapping[role]()


# Ro'yxatdan o'tmagan (guest) foydalanuvchilar ham kira oladigan tugmalar matni.
# AccessControlMiddleware shu ro'yxatga qarab tekshiradi.
PUBLIC_TEXTS = {"📰 Yangiliklar", "📅 Kurslar jadvali", "🎁 Konkurslar", "📝 Ro'yxatdan o'tish"}
