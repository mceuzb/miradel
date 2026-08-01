from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Contest, ContestResult, ContestStatus, Visitor
from bot.services.referral_service import get_leaderboard
from bot.services.visitor_service import get_visitor


async def get_all_contests(session: AsyncSession) -> list[Contest]:
    result = await session.execute(select(Contest).order_by(Contest.id.desc()))
    return list(result.scalars().all())


async def get_active_contests(session: AsyncSession) -> list[Contest]:
    result = await session.execute(select(Contest).where(Contest.status == ContestStatus.ACTIVE))
    return list(result.scalars().all())


async def create_contest(session: AsyncSession, title: str, end_date: datetime, prizes: list[dict]) -> Contest:
    contest = Contest(
        title=title,
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
    """Konkursni yakunlaydi: joriy reytingni 'muzlatib', ContestResult jadvaliga
    g'oliblarni (sovg'alari bilan) yozib qo'yadi va statusni FINISHED qiladi.
    G'oliblar ro'yxatdan o'tmagan mehmon bo'lishi ham mumkin."""
    contest = await session.get(Contest, contest_id)
    if contest is None or contest.status != ContestStatus.ACTIVE:
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
