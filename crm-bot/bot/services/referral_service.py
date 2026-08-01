from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Referral, ReferralStatus, User
from bot.services.user_service import get_user_by_telegram_id


async def capture_referral(session: AsyncSession, referred_telegram_id: int, referrer_telegram_id: int) -> None:
    """/start ref_<id> orqali kirilganda chaqiriladi. Har bir taklif qilingan odam
    faqat BIR marta, birinchi taklif qiluvchiga hisoblanadi (o'z-o'ziga taklif
    va takroriy yozuvlar oldini olinadi). Bu bosqichda hali TASDIQLANMAGAN -
    faqat kanalga a'zo bo'lgandan keyin CONFIRMED bo'ladi."""
    if referrer_telegram_id == referred_telegram_id:
        return
    referrer = await get_user_by_telegram_id(session, referrer_telegram_id)
    if referrer is None:
        return

    result = await session.execute(
        select(Referral).where(Referral.referred_telegram_id == referred_telegram_id)
    )
    if result.scalar_one_or_none() is not None:
        return

    session.add(Referral(
        referrer_id=referrer.id,
        referred_telegram_id=referred_telegram_id,
        status=ReferralStatus.PENDING,
    ))
    await session.commit()


async def try_confirm_referral(session: AsyncSession, referred_telegram_id: int) -> None:
    """Foydalanuvchi HOZIR barcha majburiy kanallarga a'zo ekani tekshirilib
    tasdiqlangandan keyin chaqiriladi (SubscriptionCheckMiddleware'dan)."""
    result = await session.execute(
        select(Referral).where(
            Referral.referred_telegram_id == referred_telegram_id,
            Referral.status == ReferralStatus.PENDING,
        )
    )
    referral = result.scalar_one_or_none()
    if referral is None:
        return
    referral.status = ReferralStatus.CONFIRMED
    referral.confirmed_at = datetime.now(timezone.utc)
    await session.commit()


async def get_leaderboard(session: AsyncSession, contest, limit: int = 100) -> list[tuple[User, int]]:
    """Berilgan konkurs oralig'ida tasdiqlangan referallar soni bo'yicha
    kamayish tartibida reyting qaytaradi: [(User, soni), ...]."""
    query = (
        select(Referral.referrer_id, func.count(Referral.id).label("cnt"))
        .where(Referral.status == ReferralStatus.CONFIRMED)
        .where(Referral.confirmed_at >= contest.start_date)
    )
    if contest.end_date:
        query = query.where(Referral.confirmed_at <= contest.end_date)
    query = query.group_by(Referral.referrer_id).order_by(func.count(Referral.id).desc()).limit(limit)

    result = await session.execute(query)
    leaderboard: list[tuple[User, int]] = []
    for referrer_id, cnt in result.all():
        user = await session.get(User, referrer_id)
        if user is not None:
            leaderboard.append((user, cnt))
    return leaderboard
