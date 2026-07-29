from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, UserRole, UserStatus


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def create_pending_user(
    session: AsyncSession, telegram_id: int, full_name: str, phone: str | None,
    referred_by: int | None = None,
) -> User:
    user = User(
        telegram_id=telegram_id,
        full_name=full_name,
        phone=phone,
        role=UserRole.STUDENT,
        status=UserStatus.PENDING,
        referred_by=referred_by,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_pending_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.status == UserStatus.PENDING))
    return list(result.scalars().all())


async def approve_user(session: AsyncSession, user_id: int, role: UserRole) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.status = UserStatus.APPROVED
    user.role = role
    await session.commit()
    await session.refresh(user)
    return user


async def reject_user(session: AsyncSession, user_id: int) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.status = UserStatus.REJECTED
    await session.commit()
    await session.refresh(user)
    return user


async def block_user(session: AsyncSession, user_id: int, blocked: bool = True) -> User | None:
    user = await session.get(User, user_id)
    if user is None:
        return None
    user.status = UserStatus.BLOCKED if blocked else UserStatus.APPROVED
    await session.commit()
    await session.refresh(user)
    return user


async def ensure_super_admin(session: AsyncSession, telegram_id: int) -> None:
    """.env dagi SUPER_ADMIN_ID bo'yicha birinchi adminni avtomatik tasdiqlangan
    holatda yaratadi (agar hali mavjud bo'lmasa)."""
    if not telegram_id:
        return
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        user = User(
            telegram_id=telegram_id,
            full_name="Super Admin",
            role=UserRole.ADMIN,
            status=UserStatus.APPROVED,
        )
        session.add(user)
        await session.commit()
    elif user.role != UserRole.ADMIN or user.status != UserStatus.APPROVED:
        user.role = UserRole.ADMIN
        user.status = UserStatus.APPROVED
        await session.commit()
