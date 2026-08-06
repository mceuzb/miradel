from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Contest, ContestParticipant, ContestResult, ContestStatus, ContestType, Visitor
from bot.services.referral_service import get_leaderboard
from bot.services.visitor_service import get_visitor


async def get_all_contests(session: AsyncSession) -> list[Contest]:
    result = await session.execute(select(Contest).order_by(Contest.id.desc()))
    return list(result.scalars().all())


async def get_active_contests(session: AsyncSession) -> list[Contest]:
    result = await session.execute(select(Contest).where(Contest.status == ContestStatus.ACTIVE))
    return list(result.scalars().all())


async def get_active_referral_contest(session: AsyncSession) -> Contest | None:
    """Referal asosidagi (eng ko'p taklif) faol konkursni qaytaradi. Bir vaqtda
    RANDOM konkurs ham faol bo'lishi mumkin - shuning uchun turi bo'yicha
    aniq filtrlanadi."""
    result = await session.execute(
        select(Contest).where(
            Contest.status == ContestStatus.ACTIVE, Contest.contest_type == ContestType.REFERRAL,
        )
    )
    return result.scalars().first()


async def create_contest(
    session: AsyncSession, title: str, end_date: datetime, prizes: list[dict], contest_type: ContestType,
) -> Contest:
    contest = Contest(
        title=title,
        contest_type=contest_type,
        start_date=datetime.now(timezone.utc),
        end_date=end_date,
        prizes={"places": prizes},
        min_requirement=1,
        status=ContestStatus.ACTIVE,
    )
    session.add(contest)
    await session.commit()
    await session.refresh(contest)
    return contest


async def finish_contest(session: AsyncSession, contest_id: int) -> Contest | None:
    """FAQAT referal turidagi konkurslar uchun - joriy reytingni 'muzlatib',
    ContestResult jadvaliga g'oliblarni (sovg'alari bilan) avtomatik yozadi."""
    contest = await session.get(Contest, contest_id)
    if contest is None or contest.status != ContestStatus.ACTIVE or contest.contest_type != ContestType.REFERRAL:
        return None

    places = contest.prizes.get("places", [])
    winners_count = len(places)
    leaderboard = await get_leaderboard(session, contest, limit=max(winners_count, 1))

    for idx, (visitor, count) in enumerate(leaderboard[:winners_count], start=1):
        prize_text = next((p["prize"] for p in places if p["rank"] == idx), None)
        session.add(ContestResult(
            contest_id=contest.id,
            winner_telegram_id=visitor.telegram_id,
            referral_count=count,
            rank=idx,
            prize=prize_text,
        ))

    contest.status = ContestStatus.FINISHED
    await session.commit()
    await session.refresh(contest)
    return contest


async def finish_random_contest(
    session: AsyncSession, contest_id: int, winners: list[tuple[int, int]],
) -> Contest | None:
    """RANDOM turdagi konkurs uchun - admin o'zi (botdan tashqarida, masalan
    random.org orqali) tanlagan g'oliblarni kiritadi. winners: [(rank, telegram_id), ...]"""
    contest = await session.get(Contest, contest_id)
    if contest is None or contest.status != ContestStatus.ACTIVE or contest.contest_type != ContestType.RANDOM:
        return None

    places = contest.prizes.get("places", [])
    for rank, telegram_id in winners:
        prize_text = next((p["prize"] for p in places if p["rank"] == rank), None)
        session.add(ContestResult(
            contest_id=contest.id,
            winner_telegram_id=telegram_id,
            referral_count=0,
            rank=rank,
            prize=prize_text,
        ))

    contest.status = ContestStatus.FINISHED
    await session.commit()
    await session.refresh(contest)
    return contest


async def get_contest_results(session: AsyncSession, contest_id: int) -> list[tuple[ContestResult, Visitor | None]]:
    result = await session.execute(
        select(ContestResult).where(ContestResult.contest_id == contest_id).order_by(ContestResult.rank)
    )
    results = list(result.scalars().all())
    paired: list[tuple[ContestResult, Visitor | None]] = []
    for r in results:
        visitor = await get_visitor(session, r.winner_telegram_id)
        paired.append((r, visitor))
    return paired


async def join_random_contest(session: AsyncSession, contest_id: int, telegram_id: int) -> bool:
    """RANDOM konkursga qo'shiladi. Allaqachon qo'shilgan bo'lsa - False
    qaytaradi (qayta yozilmaydi)."""
    existing = await session.execute(
        select(ContestParticipant).where(
            ContestParticipant.contest_id == contest_id, ContestParticipant.telegram_id == telegram_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False
    session.add(ContestParticipant(contest_id=contest_id, telegram_id=telegram_id))
    await session.commit()
    return True


async def get_contest_participants(session: AsyncSession, contest_id: int) -> list[tuple[Visitor, None]]:
    """RANDOM konkurs ishtirokchilari ro'yxati - standart (referal) konkurs
    eksporti bilan BIR XIL formatda (Excel jadval tartibi mos kelishi uchun).
    Ikkinchi element doim None - referal soni tushunchasi RANDOM konkursga
    tegishli emas."""
    result = await session.execute(
        select(ContestParticipant)
        .where(ContestParticipant.contest_id == contest_id)
        .order_by(ContestParticipant.joined_at)
    )
    participants = list(result.scalars().all())
    paired: list[tuple[Visitor, None]] = []
    for p in participants:
        visitor = await get_visitor(session, p.telegram_id)
        if visitor is not None:
            paired.append((visitor, None))
    return paired
