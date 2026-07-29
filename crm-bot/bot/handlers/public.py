from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Contest, ContestStatus, Group
from bot.middlewares.module_guard import module_guard

router = Router(name="public")


@router.message(F.text == "📰 Yangiliklar")
async def news(message: Message, **kwargs):
    # MVP: statik xabar. Keyingi bosqichda admin panelidan yangilik joylash
    # funksiyasi qo'shilganda shu joyga DB'dan so'nggi postlar chiqariladi.
    await message.answer(
        "📰 <b>Miradel Academy</b> yangiliklari\n\n"
        "Hozircha yangiliklar bo'limi to'ldirilmoqda. Tez orada bu yerda "
        "o'quv markazimizning so'nggi yangiliklarini ko'rasiz."
    )


@router.message(F.text == "📅 Kurslar jadvali")
async def course_schedule(message: Message, session: AsyncSession, **kwargs):
    result = await session.execute(select(Group).where(Group.is_archived == False))  # noqa: E712
    groups = result.scalars().all()
    if not groups:
        await message.answer("Hozircha faol kurslar mavjud emas. Tez orada yangilanadi!")
        return
    lines = [f"• <b>{g.name}</b> — {g.subject or 'yo‘nalish belgilanmagan'}" for g in groups]
    await message.answer("📅 <b>Kurslar jadvali</b>\n\n" + "\n".join(lines))


@router.message(F.text == "🎁 Konkurslar")
@module_guard("contest_module")
async def contests(message: Message, session: AsyncSession, **kwargs):
    result = await session.execute(select(Contest).where(Contest.status == ContestStatus.ACTIVE))
    active_contests = result.scalars().all()
    if not active_contests:
        await message.answer("Hozircha faol konkurslar yo'q. Tez orada e'lon qilinadi!")
        return
    lines = []
    for c in active_contests:
        lines.append(
            f"🎁 <b>{c.title}</b>\n"
            f"Boshlanishi: {c.start_date.strftime('%d.%m.%Y')}\n"
            f"Tugashi: {c.end_date.strftime('%d.%m.%Y')}"
        )
    await message.answer("\n\n".join(lines))
