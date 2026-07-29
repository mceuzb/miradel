import time

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import RequiredChannel

# Oddiy in-memory kesh: {(telegram_id, channel_username): (is_subscribed, timestamp)}
# 7.2-bo'lim: "Tekshiruv natijalari keshlanadi (masalan 5-10 daqiqaga)"
_CACHE_TTL_SECONDS = 300
_subscription_cache: dict[tuple[int, str], tuple[bool, float]] = {}


async def get_active_channels(session: AsyncSession) -> list[RequiredChannel]:
    result = await session.execute(select(RequiredChannel).where(RequiredChannel.is_active == True))  # noqa: E712
    return list(result.scalars().all())


async def is_user_subscribed_to_channel(bot: Bot, telegram_id: int, channel_username: str) -> bool:
    cache_key = (telegram_id, channel_username)
    cached = _subscription_cache.get(cache_key)
    if cached and (time.time() - cached[1]) < _CACHE_TTL_SECONDS:
        return cached[0]

    try:
        member = await bot.get_chat_member(chat_id=f"@{channel_username.lstrip('@')}", user_id=telegram_id)
        is_subscribed = member.status not in ("left", "kicked")
    except Exception:
        # Bot kanalda admin bo'lmasa yoki kanal topilmasa - xavfsiz tomonga o'tamiz
        is_subscribed = False

    _subscription_cache[cache_key] = (is_subscribed, time.time())
    return is_subscribed


async def check_all_required_channels(
    session: AsyncSession, bot: Bot, telegram_id: int
) -> list[RequiredChannel]:
    """A'zo bo'lmagan kanallar ro'yxatini qaytaradi. Bo'sh ro'yxat = hammasiga a'zo."""
    channels = await get_active_channels(session)
    not_subscribed = []
    for channel in channels:
        if not await is_user_subscribed_to_channel(bot, telegram_id, channel.channel_username):
            not_subscribed.append(channel)
    return not_subscribed
