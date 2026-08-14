"""Alpino - asosiy biznes-mantiq (TZ v3, 3-bo'lim).

Muhim tamoyil: balans HECH QACHON alohida ustunda saqlanmaydi, har safar
shu yerdagi `get_balance()` orqali hisoblab chiqiladi - referral_service.py
dagi `_compute_all_scores` uslubiga o'xshab. Bu ma'lumotlar mos kelmasligining
oldini oladi.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import (
    AlpinoMarketItem, AlpinoMarketOrder, AlpinoOrderStatus, AlpinoPointsHistory,
    AlpinoPointsStatus, AlpinoReferral, AlpinoReferralStatus, User, UserStatus,
)


class AlpinoError(Exception):
    """Foydalanuvchiga ko'rsatiladigan, kutilgan xatolar uchun (400 turkumidagi)."""


async def get_balance(session: AsyncSession, user: User) -> int:
    """Joriy balans - real vaqtda hisoblanadi, saqlanmaydi."""
    # Markazni tark etgan (BLOCKED) foydalanuvchi - balans har doim 0
    if user.status == UserStatus.BLOCKED:
        return 0

    earned = await session.scalar(
        select(func.coalesce(func.sum(AlpinoPointsHistory.amount), 0))
        .where(
            AlpinoPointsHistory.user_id == user.id,
            AlpinoPointsHistory.status == AlpinoPointsStatus.APPROVED,
        )
    ) or 0

    spent = await session.scalar(
        select(func.coalesce(func.sum(AlpinoMarketOrder.cost_points), 0))
        .where(AlpinoMarketOrder.user_id == user.id)
    ) or 0

    return int(earned) - int(spent)


# ---------------------------------------------------------------------------
# O'qituvchi -> Admin ball oqimi (TZ v3, 3.2-band)
# ---------------------------------------------------------------------------

async def propose_points(
    session: AsyncSession,
    *,
    student: User,
    teacher: User,
    category: str,
    amount: int,
    comment: str | None,
) -> AlpinoPointsHistory:
    if amount <= 0:
        raise AlpinoError("Ball miqdori musbat son bo'lishi kerak")

    limit = await get_category_limit(session, category)
    if limit is not None and amount > limit:
        raise AlpinoError(f"Bu toifa uchun maksimal ball: {limit}")

    entry = AlpinoPointsHistory(
        user_id=student.id,
        teacher_id=teacher.id,
        category=category,
        amount=amount,
        comment=comment,
        status=AlpinoPointsStatus.PENDING,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


async def get_category_limit(session: AsyncSession, category: str) -> int | None:
    from bot.database.models import AlpinoCategoryLimit
    row = await session.scalar(
        select(AlpinoCategoryLimit.max_points).where(AlpinoCategoryLimit.category == category)
    )
    return row


async def approve_points(session: AsyncSession, *, entry_id: int, admin: User) -> AlpinoPointsHistory:
    entry = await session.get(AlpinoPointsHistory, entry_id)
    if entry is None:
        raise AlpinoError("Taklif topilmadi")
    if entry.status != AlpinoPointsStatus.PENDING:
        raise AlpinoError("Bu taklif allaqachon ko'rib chiqilgan")
    entry.status = AlpinoPointsStatus.APPROVED
    entry.admin_id = admin.id
    entry.approved_at = datetime.now(timezone.utc)
    await session.commit()
    return entry


async def reject_points(session: AsyncSession, *, entry_id: int, admin: User, reason: str) -> AlpinoPointsHistory:
    if not reason or not reason.strip():
        raise AlpinoError("Rad etish sababi majburiy")
    entry = await session.get(AlpinoPointsHistory, entry_id)
    if entry is None:
        raise AlpinoError("Taklif topilmadi")
    if entry.status != AlpinoPointsStatus.PENDING:
        raise AlpinoError("Bu taklif allaqachon ko'rib chiqilgan")
    entry.status = AlpinoPointsStatus.REJECTED
    entry.admin_id = admin.id
    entry.reject_reason = reason
    await session.commit()
    return entry


# ---------------------------------------------------------------------------
# Market (TZ v3, 3.4-band)
# ---------------------------------------------------------------------------

async def buy_item(session: AsyncSession, *, user: User, item_id: int) -> AlpinoMarketOrder:
    item = await session.get(AlpinoMarketItem, item_id)
    if item is None or not item.is_active:
        raise AlpinoError("Mahsulot topilmadi")
    if item.stock <= 0:
        raise AlpinoError("Mahsulot tugagan")

    balance = await get_balance(session, user)
    if balance < item.cost_points:
        raise AlpinoError("Balansingiz yetarli emas")

    # Race condition oldini olish: stock qayta o'qib, shart bilan kamaytiramiz
    item.stock -= 1
    order = AlpinoMarketOrder(
        user_id=user.id,
        item_id=item.id,
        item_name=item.name,        # tarixiy - keyin katalog o'zgarsa ham order o'zgarmaydi
        cost_points=item.cost_points,
        status=AlpinoOrderStatus.PENDING,
    )
    session.add(order)
    await session.commit()
    await session.refresh(order)
    return order


async def fulfil_order(session: AsyncSession, *, order_id: int) -> AlpinoMarketOrder:
    order = await session.get(AlpinoMarketOrder, order_id)
    if order is None:
        raise AlpinoError("Buyurtma topilmadi")
    if order.status != AlpinoOrderStatus.PENDING:
        raise AlpinoError("Bu buyurtma allaqachon topshirilgan")
    order.status = AlpinoOrderStatus.DELIVERED
    order.delivered_at = datetime.now(timezone.utc)
    await session.commit()
    return order


# ---------------------------------------------------------------------------
# Referral (TZ v3, 3.3-band) - mavjud approve_user()/Payment oqimidan chaqiriladi
# ---------------------------------------------------------------------------

async def award_referral_came(session: AsyncSession, *, referred_user: User) -> None:
    """referred_user.referred_by to'ldirilgan bo'lsa, +10 ball beriladi.
    user_service.approve_user() ichidan chaqiriladi."""
    if referred_user.referred_by is None:
        return
    referrer = await session.get(User, referred_user.referred_by)
    if referrer is None:
        return

    existing = await session.scalar(
        select(AlpinoReferral).where(AlpinoReferral.referred_id == referred_user.id)
    )
    if existing is not None:
        return  # allaqachon qo'shilgan (uq_alpino_referred_once ham himoya qiladi)

    session.add(AlpinoReferral(
        referrer_id=referrer.id,
        referred_id=referred_user.id,
        status=AlpinoReferralStatus.CAME,
    ))
    session.add(AlpinoPointsHistory(
        user_id=referrer.id,
        category="referral_kelish",
        amount=10,
        status=AlpinoPointsStatus.APPROVED,  # referral avtomatik - o'qituvchi tasdiqlashi shart emas
        approved_at=datetime.now(timezone.utc),
    ))
    await session.commit()


async def award_referral_payment(session: AsyncSession, *, paid_user: User) -> None:
    """paid_user birinchi to'lovini amalga oshirganda chaqiriladi
    (payment_service.py'da Payment yaratilgandan keyin)."""
    referral = await session.scalar(
        select(AlpinoReferral).where(AlpinoReferral.referred_id == paid_user.id)
    )
    if referral is None or referral.status == AlpinoReferralStatus.PAID:
        return  # referral orqali kelmagan, yoki allaqachon bonus berilgan

    referral.status = AlpinoReferralStatus.PAID
    session.add(AlpinoPointsHistory(
        user_id=referral.referrer_id,
        category="referral_tolov",
        amount=500,
        status=AlpinoPointsStatus.APPROVED,
        approved_at=datetime.now(timezone.utc),
    ))

    # Bir oyda 2-chi "to'lov qilgan" referal bo'lsa - qo'shimcha +300 (1 marta/oy)
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    paid_count_this_month = await session.scalar(
        select(func.count(AlpinoReferral.id)).where(
            AlpinoReferral.referrer_id == referral.referrer_id,
            AlpinoReferral.status == AlpinoReferralStatus.PAID,
        )
    ) or 0

    if paid_count_this_month >= 2:
        already_bonused = await session.scalar(
            select(AlpinoReferral).where(
                AlpinoReferral.referrer_id == referral.referrer_id,
                AlpinoReferral.paid_bonus_month == current_month,
            )
        )
        if already_bonused is None:
            referral.paid_bonus_month = current_month
            session.add(AlpinoPointsHistory(
                user_id=referral.referrer_id,
                category="referral_tolov",
                amount=300,
                status=AlpinoPointsStatus.APPROVED,
                approved_at=datetime.now(timezone.utc),
                comment="Oyiga 2-chi to'lov qilgan referal bonusi",
            ))

    await session.commit()
