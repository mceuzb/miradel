from sqlalchemy import select
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
