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


async def revoke_referral(session: AsyncSession, referred_telegram_id: int) -> Referral | None:
    """Taklif qilingan odam kanaldan chiqib ketganda chaqiriladi (chat_member
    eventidan). Faqat HOZIR CONFIRMED bo'lgan referalni bekor qiladi - eski
    (bu funksiya qo'shilishidan oldingi) holatlarga tegmaydi, chunki Telegram
    faqat HOZIRGI chiqib ketish hodisasi haqida xabar beradi, orqaga qarab
    emas. Bekor qilingan referal bo'lsa - obyektni qaytaradi (referrerga
    xabar berish uchun), aks holda None."""
    result = await session.execute(
        select(Referral).where(
            Referral.referred_telegram_id == referred_telegram_id,
            Referral.status == ReferralStatus.CONFIRMED,
        )
    )
    referral = result.scalar_one_or_none()
    if referral is None:
        return None
    referral.status = ReferralStatus.REVOKED
    referral.revoked_at = datetime.now(timezone.utc)
    await session.commit()
    return referral


async def restore_referral(session: AsyncSession, referred_telegram_id: int) -> Referral | None:
    """Avval REVOKED qilingan (chiqib ketgan) odam barcha majburiy kanallarga
    QAYTA a'zo bo'lsa chaqiriladi - ball qaytarib beriladi (adolatli, vaqtincha
    chiqib ketish umrbod jazolanmasligi kerak). Faqat REVOKED holatidagi
    referalni CONFIRMED'ga qaytaradi."""
    result = await session.execute(
        select(Referral).where(
            Referral.referred_telegram_id == referred_telegram_id,
            Referral.status == ReferralStatus.REVOKED,
        )
    )
    referral = result.scalar_one_or_none()
    if referral is None:
        return None
    referral.status = ReferralStatus.CONFIRMED
    referral.confirmed_at = datetime.now(timezone.utc)
    referral.revoked_at = None
    await session.commit()
    return referral


async def get_user_stats(session: AsyncSession, contest, telegram_id: int) -> tuple[int, int] | None:
    """Berilgan foydalanuvchining shu konkursdagi o'rni va tasdiqlangan referal
    sonini qaytaradi: (o'rin, soni). Agar birorta ham tasdiqlangan referali
    bo'lmasa - None qaytaradi."""
    base = (
        select(Referral.referrer_telegram_id, func.count(Referral.id).label("cnt"))
        .where(Referral.status == ReferralStatus.CONFIRMED)
        .where(Referral.confirmed_at >= contest.start_date)
    )
    if contest.end_date:
        base = base.where(Referral.confirmed_at <= contest.end_date)
    subq = base.group_by(Referral.referrer_telegram_id).subquery()

    result = await session.execute(
        select(subq.c.cnt).where(subq.c.referrer_telegram_id == telegram_id)
    )
    user_count = result.scalar_one_or_none()
    if user_count is None:
        return None

    result = await session.execute(
        select(func.count()).select_from(subq).where(subq.c.cnt > user_count)
    )
    higher_count = result.scalar_one()
    return (higher_count + 1, user_count)


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
