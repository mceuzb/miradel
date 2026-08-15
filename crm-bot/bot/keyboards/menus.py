from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_config
from bot.database.models import User, UserRole
from bot.services.alpino_access import alpino_access_allowed

# MUHIM: Telegram rasman hujjatlashtirgan xatti-harakat - agar Mini App
# ReplyKeyboardButton (pastki klaviatura) orqali ochilsa, initData HAR DOIM
# BO'SH keladi (https://core.telegram.org/bots/webapps#webappinitdata:
# "It is empty if the Mini App was launched from a keyboard button").
# Shuning uchun "⛰️ Alpino" endi oddiy MATN tugmasi - uni bosganda handler
# alohida xabar orqali INLINE web_app tugmasini yuboradi (bot/handlers/common.py,
# alpino_open_webapp), faqat o'sha yerda initData to'g'ri keladi.
ALPINO_BUTTON_TEXT = "⛰️ Alpino"


async def _alpino_row(session: AsyncSession, user: User) -> list[KeyboardButton]:
    """Alpino - alohida, mustaqil mini-app.
    Ko'rinishi uchun IKKI shart bajarilishi kerak:
    1) domen sozlangan bo'lishi (Railway'da 'Generate Domain')
    2) alpino_access_allowed() - Admin uchun har doim True, o'qituvchi uchun
       modul yoqilgan bo'lsa, o'quvchi uchun modul yoqilgan VA o'qituvchi
       tomonidan qo'lda qo'shilgan bo'lishi kerak (TZ v3, 1.2-band + login/parol
       tizimi)."""
    url = get_config().get_alpino_url()
    if not url:
        return []
    if not await alpino_access_allowed(session, user):
        return []
    # DIQQAT: bu yerda web_app=... QASDAN ishlatilmaydi - sababi yuqorida.
    return [KeyboardButton(text=ALPINO_BUTTON_TEXT)]


def contact_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def guest_menu_kb() -> ReplyKeyboardMarkup:
    """Ro'yxatdan o'tmagan (guest) foydalanuvchilar uchun.
    Alpino BU YERDA HECH QACHON ko'rsatilmaydi (TZ v3, 1.1-band:
    'faqat ro'yxatdan o'tganlar') - shuning uchun session/role shart emas."""
    rows = [
        [KeyboardButton(text="📰 Yangiliklar"), KeyboardButton(text="📅 Kurslar jadvali")],
        [KeyboardButton(text="🎁 Konkurslar"), KeyboardButton(text="🏆 Reyting")],
        [KeyboardButton(text="🔗 Do'stlarni taklif qilish")],
        [KeyboardButton(text="🎓 Kursga yozilish")],
        [KeyboardButton(text="🔑 Login orqali kirish")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


async def admin_menu_kb(session: AsyncSession, user: User) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🆕 Yangi so'rovlar"), KeyboardButton(text="👩‍🎓 O'qituvchi qo'shganlar")],
        [KeyboardButton(text="⚙️ Modullar"), KeyboardButton(text="👥 Guruhlar")],
        [KeyboardButton(text="📊 Hisobotlar"), KeyboardButton(text="📢 Majburiy kanallar")],
        [KeyboardButton(text="🎛 Konkurslarni boshqarish"), KeyboardButton(text="📢 Ommaviy xabar")],
        [KeyboardButton(text="🎫 Referal kartalar")],
    ]
    alpino = await _alpino_row(session, user)
    if alpino:
        rows.append(alpino)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


async def teacher_menu_kb(session: AsyncSession, user: User) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="👥 Guruhlarim"), KeyboardButton(text="✅ Davomat")],
        [KeyboardButton(text="📝 Vazifa berish"), KeyboardButton(text="📥 Topshiriqlar")],
        [KeyboardButton(text="➕ O'quvchi qo'shish")],
    ]
    alpino = await _alpino_row(session, user)
    if alpino:
        rows.append(alpino)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


async def student_menu_kb(session: AsyncSession, user: User) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="👤 Kabinetim"), KeyboardButton(text="📝 Vazifalarim")],
        [KeyboardButton(text="📅 Dars jadvali"), KeyboardButton(text="📈 Davomatim")],
        [KeyboardButton(text="🎁 Konkurslar"), KeyboardButton(text="🏆 Reyting")],
        [KeyboardButton(text="🔗 Do'stlarni taklif qilish")],
    ]
    alpino = await _alpino_row(session, user)
    if alpino:
        rows.append(alpino)
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


async def menu_for_role(session: AsyncSession, user: User) -> ReplyKeyboardMarkup:
    mapping = {
        UserRole.ADMIN: admin_menu_kb,
        UserRole.TEACHER: teacher_menu_kb,
        UserRole.STUDENT: student_menu_kb,
    }
    return await mapping[user.role](session, user)


# Ro'yxatdan o'tmagan (guest) foydalanuvchilar ham kira oladigan tugmalar matni.
# AccessControlMiddleware shu ro'yxatga qarab tekshiradi.
PUBLIC_TEXTS = {
    "📰 Yangiliklar", "📅 Kurslar jadvali", "🎁 Konkurslar", "🏆 Reyting",
    "🔗 Do'stlarni taklif qilish", "🎓 Kursga yozilish", "🔑 Login orqali kirish",
}

# Ro'yxatdan o'tmagan (guest) foydalanuvchilar ham bosa oladigan INLINE
# tugmalar (callback_data). AccessControlMiddleware shu ro'yxatga qarab
# tekshiradi - matn tugmalaridan farqli o'laroq, callbacklar avval bu yerda
# alohida tasdiqlanmasa, bloklanib qolar edi.
PUBLIC_CALLBACK_DATA = {"check_subscription", "get_referral_link", "referral_card_info", "referral_card_order"}
PUBLIC_CALLBACK_PREFIXES = ("join_random:", "broadcast_interest:")
