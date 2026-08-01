from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Referral, ReferralStatus, Visitor
from bot.services.visitor_service import get_visitor


async def capture_referral(session: AsyncSession, referred_telegram_id: int, referrer_telegram_id: int) -> None:
    """/start ref_<id> orqali kirilganda chaqiriladi. Taklif qiluvchi ro'yxatdan
    o'tgan yoki oddiy mehmon bo'lishi mumkin - faqat botga bir marta kirgan
    bo'lishi (Visitor jadvalida mavjud bo'lishi) kifoya. Har bir taklif
    qilingan odam faqat BIR marta, birinchi taklif qiluvchiga hisoblanadi.
    Bu bosqichda hali TASDIQLANMAGAN - faqat kanalga a'zo bo'lgandan keyin
    CONFIRMED bo'ladi."""
    if referrer_telegram_id == referred_telegram_id:
        return
    referrer = await get_visitor(session, referrer_telegram_id)
    if referrer is None:
        return

    result = await session.execute(
        select(Referral).where(Referral.referred_telegram_id == referred_telegram_id)
    )
    if result.scalar_one_or_none() is not None:
        return

    session.add(Referral(
        referrer_telegram_id=referrer_telegram_id,
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


async def get_leaderboard(session: AsyncSession, contest, limit: int | None = 100) -> list[tuple[Visitor, int]]:
    """Berilgan konkurs oralig'ida tasdiqlangan referallar soni bo'yicha
    kamayish tartibida reyting qaytaradi: [(Visitor, soni), ...].
    limit=None bo'lsa - CHEKLOVSIZ, barcha ishtirokchilar qaytariladi."""
    query = (
        select(Referral.referrer_telegram_id, func.count(Referral.id).label("cnt"))
        .where(Referral.status == ReferralStatus.CONFIRMED)
        .where(Referral.confirmed_at >= contest.start_date)
    )
    if contest.end_date:
        query = query.where(Referral.confirmed_at <= contest.end_date)
    query = query.group_by(Referral.referrer_telegram_id).order_by(func.count(Referral.id).desc())
    if limit is not None:
        query = query.limit(limit)

    result = await session.execute(query)
    leaderboard: list[tuple[Visitor, int]] = []
    for referrer_telegram_id, cnt in result.all():
        visitor = await get_visitor(session, referrer_telegram_id)
        if visitor is not None:
            leaderboard.append((visitor, cnt))
    return leaderboard
