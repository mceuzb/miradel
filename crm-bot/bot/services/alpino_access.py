"""Alpino uchun maxsus ruxsat tekshiruvi (TZ v3, 1.2-band).

Oddiy `module_guard` dekoratoridan farqi: Admin modul o'chiq (`is_enabled=False`)
bo'lsa ham har doim kira oladi - shu orqali siz Alpino'ni production'da,
real bazada, boshqa hech kimga bildirmasdan sinab ko'rishingiz mumkin.
O'qituvchi va o'quvchi esa faqat modul yoqilgandan keyin kira oladi.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, UserRole
from bot.services.module_service import is_module_enabled

ALPINO_MODULE_KEY = "alpino_module"

# Faqat shu manbadan kelgan (o'qituvchi ism-familiya+guruh bilan qo'lda
# qo'shgan) o'quvchilar Alpino'dan foydalana oladi - Telegram orqali o'zi
# yozilgan ("telegram_lead") o'quvchilar bunga kirmaydi, hatto admin
# tasdiqlagan bo'lsa ham. O'qituvchi/admin rollariga bu cheklov tegishli emas.
TEACHER_ENROLLED_SOURCE = "teacher_enrolled"


async def alpino_access_allowed(session: AsyncSession, user: User) -> bool:
    """Admin - har doim True (sinov uchun). O'qituvchi - modul yoqilgan bo'lsa.
    O'quvchi - modul yoqilgan BO'LISHI VA o'qituvchi tomonidan qo'lda
    qo'shilgan (source=teacher_enrolled) bo'lishi kerak."""
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.STUDENT and user.source != TEACHER_ENROLLED_SOURCE:
        return False
    return await is_module_enabled(session, ALPINO_MODULE_KEY)
