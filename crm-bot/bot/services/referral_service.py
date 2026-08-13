from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Referral, ReferralPointsLedger, ReferralStatus, Visitor
from bot.services.visitor_service import get_visitor

# Zanjir bo'ylab yuqoriga chiqishda cheksiz aylanib qolmaslik uchun xavfsizlik chegarasi
_MAX_CHAIN_DEPTH = 50


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


async def _award_chain_points(session: AsyncSession, referred_telegram_id: int, when: datetime) -> None:
    """🔥 ZANJIRLI BALL TIZIMI: yangi odam tasdiqlanganda, zanjirdagi HAR BIR
    ajdodga o'zining shu odamdan necha bosqich uzoqligiga teng ball beriladi
    (to'g'ridan-to'g'ri taklif qiluvchi = 1 ball, uni taklif qilgan = 2 ball,
    va hokazo). Faqat CONFIRMED (tasdiqlangan) zanjir bo'ylab yuriladi -
    tasdiqlanmagan yoki uzilgan joyda to'xtaydi."""
    current = referred_telegram_id
    visited = {referred_telegram_id}
    distance = 1

    while distance <= _MAX_CHAIN_DEPTH:
        result = await session.execute(
            select(Referral).where(
                Referral.referred_telegram_id == current,
                Referral.status == ReferralStatus.CONFIRMED,
            )
        )
        edge = result.scalar_one_or_none()
        if edge is None:
            break

        ancestor = edge.referrer_telegram_id
        if ancestor in visited:
            break  # halqa (cycle) - xavfsizlik uchun to'xtatiladi

        session.add(ReferralPointsLedger(
            recipient_telegram_id=ancestor,
            points=distance,
            source_referred_telegram_id=referred_telegram_id,
            distance=distance,
            created_at=when,
        ))
        visited.add(ancestor)
        current = ancestor
        distance += 1

    await session.commit()


async def try_confirm_referral(session: AsyncSession, referred_telegram_id: int) -> None:
    """Foydalanuvchi HOZIR barcha majburiy kanallarga a'zo ekani tekshirilib
    tasdiqlangandan keyin chaqiriladi (SubscriptionCheckMiddleware'dan).
    Bu YANGI (birinchi marta) tasdiqlanish - shuning uchun zanjirli ball
    tizimi shu yerda ishga tushadi."""
    result = await session.execute(
        select(Referral).where(
            Referral.referred_telegram_id == referred_telegram_id,
            Referral.status == ReferralStatus.PENDING,
        )
    )
    referral = result.scalar_one_or_none()
    if referral is None:
        return

    now = datetime.now(timezone.utc)
    referral.status = ReferralStatus.CONFIRMED
    referral.confirmed_at = now
    referral.chain_processed = True
    await session.commit()

    await _award_chain_points(session, referred_telegram_id, now)


async def revoke_referral(session: AsyncSession, referred_telegram_id: int) -> Referral | None:
    """Taklif qilingan odam kanaldan chiqib ketganda chaqiriladi (chat_member
    eventidan). Faqat HOZIR CONFIRMED bo'lgan referalni bekor qiladi - eski
    (bu funksiya qo'shilishidan oldingi) holatlarga tegmaydi, chunki Telegram
    faqat HOZIRGI chiqib ketish hodisasi haqida xabar beradi, orqaga qarab
    emas. Bekor qilingan referal bo'lsa - obyektni qaytaradi (referrerga
    xabar berish uchun), aks holda None.

    MUHIM: agar bu odam zanjirda ishtirok etib, ajdodlariga ball bergan bo'lsa
    (ReferralPointsLedger'da source_referred_telegram_id sifatida qatnashgan
    bo'lsa) - o'sha ballar HAM vaqtincha bekor qilinadi (active=False), toki
    u qaytadan a'zo bo'lguncha."""
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

    ledger_result = await session.execute(
        select(ReferralPointsLedger).where(
            ReferralPointsLedger.source_referred_telegram_id == referred_telegram_id,
            ReferralPointsLedger.active == True,  # noqa: E712
        )
    )
    for entry in ledger_result.scalars().all():
        entry.active = False

    await session.commit()
    return referral


async def restore_referral(session: AsyncSession, referred_telegram_id: int) -> Referral | None:
    """Avval REVOKED qilingan (chiqib ketgan) odam barcha majburiy kanallarga
    QAYTA a'zo bo'lsa chaqiriladi. FAQAT statusni CONFIRMED'ga qaytaradi va
    avval bekor qilingan zanjir ballarini TIKLAYDI - zanjirli ball tizimi
    QAYTA ISHGA TUSHMAYDI (qayta qo'shilish YANGI ball bermaydi, faqat
    avvalgi ballari qaytariladi)."""
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

    ledger_result = await session.execute(
        select(ReferralPointsLedger).where(
            ReferralPointsLedger.source_referred_telegram_id == referred_telegram_id,
            ReferralPointsLedger.active == False,  # noqa: E712
        )
    )
    for entry in ledger_result.scalars().all():
        entry.active = True

    await session.commit()
    return referral


async def _compute_all_scores(session: AsyncSession, contest) -> dict[int, int]:
    """Har bir foydalanuvchining jami ballini hisoblaydi:
    - ESKI (chain_processed=False) tasdiqlangan to'g'ridan-to'g'ri referallar - 1 ball har biri
    - YANGI (zanjirli tizim orqali) berilgan ballar - ReferralPointsLedger'dan yig'indi
    Ikkalasi ham berilgan konkurs vaqt oralig'iga qarab filtrlanadi."""
    scores: dict[int, int] = {}

    legacy_query = (
        select(Referral.referrer_telegram_id, func.count(Referral.id).label("cnt"))
        .where(Referral.status == ReferralStatus.CONFIRMED)
        .where(Referral.chain_processed == False)  # noqa: E712
        .where(Referral.confirmed_at >= contest.start_date)
    )
    if contest.end_date:
        legacy_query = legacy_query.where(Referral.confirmed_at <= contest.end_date)
    legacy_query = legacy_query.group_by(Referral.referrer_telegram_id)

    result = await session.execute(legacy_query)
    for telegram_id, cnt in result.all():
        scores[telegram_id] = scores.get(telegram_id, 0) + cnt

    ledger_query = (
        select(ReferralPointsLedger.recipient_telegram_id, func.sum(ReferralPointsLedger.points).label("pts"))
        .where(ReferralPointsLedger.active == True)  # noqa: E712
        .where(ReferralPointsLedger.created_at >= contest.start_date)
    )
    if contest.end_date:
        ledger_query = ledger_query.where(ReferralPointsLedger.created_at <= contest.end_date)
    ledger_query = ledger_query.group_by(ReferralPointsLedger.recipient_telegram_id)

    result = await session.execute(ledger_query)
    for telegram_id, pts in result.all():
        scores[telegram_id] = scores.get(telegram_id, 0) + int(pts)

    return scores


async def get_user_stats(session: AsyncSession, contest, telegram_id: int) -> tuple[int, int] | None:
    """Berilgan foydalanuvchining shu konkursdagi o'rni va jami ballini
    qaytaradi: (o'rin, ball). Agar birorta ham balli bo'lmasa - None."""
    scores = await _compute_all_scores(session, contest)
    user_score = scores.get(telegram_id)
    if user_score is None:
        return None
    higher_count = sum(1 for s in scores.values() if s > user_score)
    return (higher_count + 1, user_score)


async def get_leaderboard(session: AsyncSession, contest, limit: int | None = 100) -> list[tuple[Visitor, int]]:
    """Berilgan konkurs oralig'ida jami ball bo'yicha kamayish tartibida
    reyting qaytaradi: [(Visitor, ball), ...].
    limit=None bo'lsa - CHEKLOVSIZ, barcha ishtirokchilar qaytariladi."""
    scores = await _compute_all_scores(session, contest)
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if limit is not None:
        ranked = ranked[:limit]

    leaderboard: list[tuple[Visitor, int]] = []
    for telegram_id, score in ranked:
        visitor = await get_visitor(session, telegram_id)
        if visitor is not None:
            leaderboard.append((visitor, score))
    return leaderboard
