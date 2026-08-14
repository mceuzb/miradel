"""Alpino uchun maxsus ruxsat tekshiruvi (TZ v3, 1.2-band).

Oddiy `module_guard` dekoratoridan farqi: Admin modul o'chiq (`is_enabled=False`)
bo'lsa ham har doim kira oladi - shu orqali siz Alpino'ni production'da,
real bazada, boshqa hech kimga bildirmasdan sinab ko'rishingiz mumkin.
O'qituvchi va o'quvchi esa faqat modul yoqilgandan keyin kira oladi.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import UserRole
from bot.services.module_service import is_module_enabled

ALPINO_MODULE_KEY = "alpino_module"


async def alpino_access_allowed(session: AsyncSession, role: UserRole) -> bool:
    """Admin - har doim True (sinov uchun). Boshqalar - faqat modul yoqilgan bo'lsa."""
    if role == UserRole.ADMIN:
        return True
    return await is_module_enabled(session, ALPINO_MODULE_KEY)
