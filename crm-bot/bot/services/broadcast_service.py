import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.engine import async_session
from bot.database.models import Broadcast, BroadcastClick, BroadcastLead, Visitor

logger = logging.getLogger(__name__)

# Telegram flood-limitiga tortilib qolmaslik uchun: bir vaqtda 5 tadan,
# har bir partiyadan keyin 1 soniya kutiladi (~5 xabar/soniya)
BATCH_SIZE = 5
BATCH_DELAY_SECONDS = 1.0


async def create_broadcast(session: AsyncSession, admin_id: int, text: str, group_id: int | None) -> Broadcast:
    broadcast = Broadcast(admin_id=admin_id, text=text, group_id=group_id, is_sending=True)
    session.add(broadcast)
    await session.commit()
    await session.refresh(broadcast)
    return broadcast


async def get_all_broadcasts(session: AsyncSession) -> list[Broadcast]:
    result = await session.execute(select(Broadcast).order_by(Broadcast.id.desc()))
    return list(result.scalars().all())


async def get_broadcast(session: AsyncSession, broadcast_id: int) -> Broadcast | None:
    return await session.get(Broadcast, broadcast_id)


async def record_click(session: AsyncSession, broadcast_id: int, telegram_id: int) -> bool:
    existing = await session.execute(
        select(BroadcastClick).where(
            BroadcastClick.broadcast_id == broadcast_id, BroadcastClick.telegram_id == telegram_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False
    session.add(BroadcastClick(broadcast_id=broadcast_id, telegram_id=telegram_id))
    await session.commit()
    return True


async def save_lead(
    session: AsyncSession, broadcast_id: int, telegram_id: int, full_name: str, phone: str,
) -> None:
    existing = await session.execute(
        select(BroadcastLead).where(
            BroadcastLead.broadcast_id == broadcast_id, BroadcastLead.telegram_id == telegram_id,
        )
    )
    lead = existing.scalar_one_or_none()
    if lead is not None:
        lead.full_name = full_name
        lead.phone = phone
    else:
        session.add(BroadcastLead(
            broadcast_id=broadcast_id, telegram_id=telegram_id, full_name=full_name, phone=phone,
        ))
    await session.commit()


async def get_stats(session: AsyncSession, broadcast_id: int) -> dict:
    broadcast = await session.get(Broadcast, broadcast_id)
    clicks = await session.execute(
        select(BroadcastClick).where(BroadcastClick.broadcast_id == broadcast_id)
    )
    leads = await session.execute(
        select(BroadcastLead).where(BroadcastLead.broadcast_id == broadcast_id)
    )
    return {
        "targeted": broadcast.total_targeted if broadcast else 0,
        "sent": broadcast.sent_count if broadcast else 0,
        "failed": broadcast.failed_count if broadcast else 0,
        "clicked": len(list(clicks.scalars().all())),
        "leads": len(list(leads.scalars().all())),
        "is_sending": broadcast.is_sending if broadcast else False,
    }


async def get_leads(session: AsyncSession, broadcast_id: int) -> list[BroadcastLead]:
    result = await session.execute(
        select(BroadcastLead).where(BroadcastLead.broadcast_id == broadcast_id).order_by(BroadcastLead.created_at)
    )
    return list(result.scalars().all())


async def run_broadcast(bot: Bot, broadcast_id: int, admin_telegram_id: int) -> None:
    """Fonda ishlaydi (asyncio.create_task orqali chaqiriladi) - shuning uchun
    o'z DB sessiyasini o'zi ochadi. Har 1 soniyada 5 tadan xabar yuboriladi,
    Telegram flood-limitiga tortilmaslik uchun."""
    async with async_session() as session:
        broadcast = await session.get(Broadcast, broadcast_id)
        if broadcast is None:
            return

        result = await session.execute(select(Visitor.telegram_id))
        targets = [row[0] for row in result.all()]
        broadcast.total_targeted = len(targets)
        await session.commit()

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📚 Batafsil / Qiziqaman", callback_data=f"broadcast_interest:{broadcast_id}")
        ]])

        sent = 0
        failed = 0
        for i in range(0, len(targets), BATCH_SIZE):
            batch = targets[i:i + BATCH_SIZE]
            results = await asyncio.gather(
                *(bot.send_message(tg_id, broadcast.text, reply_markup=keyboard) for tg_id in batch),
                return_exceptions=True,
            )
            for r in results:
                if isinstance(r, TelegramRetryAfter):
                    await asyncio.sleep(r.retry_after)
                    failed += 1
                elif isinstance(r, Exception):
                    failed += 1
                else:
                    sent += 1
            await asyncio.sleep(BATCH_DELAY_SECONDS)

        broadcast.sent_count = sent
        broadcast.failed_count = failed
        broadcast.is_sending = False
        await session.commit()

        try:
            await bot.send_message(
                admin_telegram_id,
                f"✅ Ommaviy xabar yuborish tugadi!\n\n"
                f"Jami maqsad: {len(targets)} ta\n"
                f"Yuborildi: {sent} ta\n"
                f"Yuborilmadi (bloklagan/o'chirgan): {failed} ta",
            )
        except Exception:
            logger.exception("Ommaviy xabar yakunida adminga xabar berib bo'lmadi")
