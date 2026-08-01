from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Contest, ContestStatus, Group
from bot.middlewares.module_guard import module_guard
from bot.services.referral_service import get_leaderboard

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


@router.message(F.text == "🏆 Reyting")
@module_guard("contest_module")
async def public_rating(message: Message, session: AsyncSession, **kwargs):
    # Ommaviy reyting - faqat ism-familiya ko'rsatiladi (username/nickname yo'q).
    # Kengaytirilgan (ism + nickname) versiya faqat admin panelida ko'rinadi.
    result = await session.execute(select(Contest).where(Contest.status == ContestStatus.ACTIVE))
    active = result.scalars().first()
    if active is None:
        await message.answer("Hozircha faol konkurs yo'q.")
        return

    leaderboard = await get_leaderboard(session, active, limit=100)
    if not leaderboard:
        await message.answer(
            f"🏆 <b>{active.title}</b>\n\n"
            "Hali hech kim do'st taklif qilmagan. Birinchi bo'lib boshlang!"
        )
        return

    lines = [f"{i}. {v.full_name} — {count} ta" for i, (v, count) in enumerate(leaderboard, start=1)]
    await message.answer(f"🏆 <b>{active.title}</b> reytingi (Top {len(lines)})\n\n" + "\n".join(lines))


@router.message(F.text == "🔗 Do'stlarni taklif qilish")
@module_guard("contest_module")
async def my_referral_link(message: Message, **kwargs):
    # Hamma - hatto ro'yxatdan o'tmagan mehmon ham - taklif havolasiga ega
    # bo'lishi va konkursda qatnashishi mumkin (Visitor jadvali orqali kuzatiladi).
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{message.from_user.id}"
    await message.answer(
        "🔗 <b>Sizning shaxsiy taklif havolangiz</b>\n\n"
        f"{link}\n\n"
        "Bu havola orqali kirgan har bir do'stingiz botni ishga tushirib, "
        "barcha majburiy kanallarga a'zo bo'lsagina konkurs reytingingizga "
        "qo'shiladi. Reytingni \"🏆 Reyting\" tugmasidan kuzatib boring!"
    )
