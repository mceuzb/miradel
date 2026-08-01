from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Visitor


async def get_visitor(session: AsyncSession, telegram_id: int) -> Visitor | None:
    result = await session.execute(select(Visitor).where(Visitor.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def upsert_visitor(session: AsyncSession, telegram_id: int, full_name: str, username: str | None) -> None:
    """Har bir /start yoki tugma bosilganda chaqiriladi - botga kirgan HAR
    BIR odamni (ro'yxatdan o'tgan yoki mehmon) qayd etadi. Bu referal/konkurs
    tizimi uchun yagona ism/username manbai."""
    visitor = await get_visitor(session, telegram_id)
    if visitor is None:
        session.add(Visitor(telegram_id=telegram_id, full_name=full_name, username=username))
        await session.commit()
    elif visitor.full_name != full_name or visitor.username != username:
        visitor.full_name = full_name
        visitor.username = username
        await session.commit()
