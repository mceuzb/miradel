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


async def alpino_access_allowed(session: AsyncSession, user: User) -> bool:
    """Admin - har doim True (sinov uchun). O'qituvchi - modul yoqilgan bo'lsa.
    O'quvchi - modul yoqilgan BO'LISHI VA login+parolini bot orqali
    tasdiqlagan (alpino_verified=True) bo'lishi kerak - bu login/parolni
    o'qituvchi/admin bergan, botda "🔑 Login orqali kirish" yoki
    "🔑 Alpino kodini kiritish" orqali kiritilgan bo'ladi
    (bot/services/teacher_student_service.link_telegram_by_credentials)."""
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.STUDENT and not user.alpino_verified:
        return False
    return await is_module_enabled(session, ALPINO_MODULE_KEY)
