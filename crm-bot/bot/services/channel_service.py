from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import RequiredChannel


async def get_all_channels(session: AsyncSession) -> list[RequiredChannel]:
    result = await session.execute(select(RequiredChannel).order_by(RequiredChannel.id))
    return list(result.scalars().all())


async def add_channel(session: AsyncSession, username: str, title: str | None = None) -> RequiredChannel:
    channel = RequiredChannel(
        channel_username=username.lstrip("@"),
        channel_title=title or username.lstrip("@"),
        is_active=True,
    )
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


async def is_required_channel(session: AsyncSession, username: str | None) -> bool:
    """chat_member eventidan kelgan kanal bizning majburiy kanallar
    ro'yxatimizga tegishlimi - yo'qmi, shuni tekshiradi (boshqa,
    aloqasi yo'q guruh/kanallardagi hodisalarga reaksiya bermaslik uchun)."""
    if not username:
        return False
    username = username.lstrip("@").lower()
    result = await session.execute(
        select(RequiredChannel.id).where(
            RequiredChannel.is_active == True,  # noqa: E712
            func.lower(RequiredChannel.channel_username) == username,
        )
    )
    return result.scalar_one_or_none() is not None


async def toggle_channel(session: AsyncSession, channel_id: int) -> RequiredChannel | None:
    channel = await session.get(RequiredChannel, channel_id)
    if channel is None:
        return None
    channel.is_active = not channel.is_active
    await session.commit()
    await session.refresh(channel)
    return channel


async def delete_channel(session: AsyncSession, channel_id: int) -> bool:
    channel = await session.get(RequiredChannel, channel_id)
    if channel is None:
        return False
    await session.delete(channel)
    await session.commit()
    return True
