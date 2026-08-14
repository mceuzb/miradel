from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    AlpinoMarketOrder, AlpinoOrderStatus, AlpinoPointsHistory, AlpinoPointsStatus,
    User, UserRole, UserStatus,
)


async def get_active_user(session: AsyncSession, telegram_id: int) -> User | None:
    """Alpino uchun faqat TASDIQLANGAN foydalanuvchi 'haqiqiy' hisoblanadi.
    Ro'yxatdan o'tmagan yoki hali tasdiqlanmagan bo'lsa - None (ya'ni 'User' roli)."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id, User.status == UserStatus.APPROVED)
    )
    return result.scalar_one_or_none()


async def get_points_balance(session: AsyncSession, user_id: int) -> int:
    """Jami ball = tasdiqlangan ballar yig'indisi - marketdan sarflangan ballar.

    ESLATMA: TZ'dagi 'markazni tark etsa 0 ga tushadi' qoidasi hali
    qo'shilmagan - bu keyingi bosqichda, o'quvchi holati (faol/tark etgan)
    tizimga ulanganda amalga oshiriladi."""
    earned_result = await session.execute(
        select(func.coalesce(func.sum(AlpinoPointsHistory.amount), 0)).where(
            AlpinoPointsHistory.user_id == user_id,
            AlpinoPointsHistory.status == AlpinoPointsStatus.APPROVED,
        )
    )
    earned = earned_result.scalar_one()

    spent_result = await session.execute(
        select(func.coalesce(func.sum(AlpinoMarketOrder.cost_points), 0)).where(
            AlpinoMarketOrder.user_id == user_id,
        )
    )
    spent = spent_result.scalar_one()

    return int(earned) - int(spent)


async def get_rank(session: AsyncSession, user_id: int, balance: int) -> int:
    """Barcha o'quvchilar orasida balансга ko'ra o'rin (1-o'rin = eng ko'p ball)."""
    result = await session.execute(select(User.id).where(User.role == UserRole.STUDENT, User.status == UserStatus.APPROVED))
    all_student_ids = [row[0] for row in result.all()]

    higher = 0
    for sid in all_student_ids:
        if sid == user_id:
            continue
        other_balance = await get_points_balance(session, sid)
        if other_balance > balance:
            higher += 1
    return higher + 1


def resolve_role(user: User | None) -> str:
    """TZ 3.3-bo'lim: 4 ta rol - user/o'quvchi/o'qituvchi/admin."""
    if user is None:
        return "user"
    if user.role == UserRole.ADMIN:
        return "admin"
    if user.role == UserRole.TEACHER:
        return "teacher"
    return "student"


async def get_pending_points(session: AsyncSession, user_id: int) -> list[AlpinoPointsHistory]:
    result = await session.execute(
        select(AlpinoPointsHistory).where(
            AlpinoPointsHistory.user_id == user_id,
            AlpinoPointsHistory.status == AlpinoPointsStatus.PENDING,
        ).order_by(AlpinoPointsHistory.created_at.desc())
    )
    return list(result.scalars().all())


async def get_points_history(session: AsyncSession, user_id: int, limit: int = 50) -> list[AlpinoPointsHistory]:
    result = await session.execute(
        select(AlpinoPointsHistory).where(AlpinoPointsHistory.user_id == user_id)
        .order_by(AlpinoPointsHistory.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())
