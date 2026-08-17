from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Contest, ContestStatus, Group, GroupEnrollmentStatus
from bot.keyboards.admin_kb import ENROLLMENT_STATUS_LABELS
from bot.keyboards.public_contest_kb import public_contests_kb
from bot.middlewares.module_guard import module_guard
from bot.services.contest_service import get_active_referral_contest, join_random_contest
from bot.services.referral_service import get_leaderboard, get_user_stats

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
    # Faqat qabul OCHIQ bo'lgan (CLOSED bo'lmagan) va arxivlanmagan guruhlar ko'rsatiladi
    result = await session.execute(
        select(Group).where(
            Group.is_archived == False,  # noqa: E712
            Group.enrollment_status != GroupEnrollmentStatus.CLOSED,
        )
    )
    groups = result.scalars().all()
    if not groups:
        await message.answer("Hozircha qabul ochiq kurslar mavjud emas. Tez orada yangilanadi!")
        return
    lines = [
        f"{ENROLLMENT_STATUS_LABELS[g.enrollment_status]}\n<b>{g.name}</b> — {g.subject or 'yo‘nalish belgilanmagan'}"
        for g in groups
    ]
    await message.answer("📅 <b>Kurslar jadvali</b>\n\n" + "\n\n".join(lines))


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
    await message.answer(
        "\n\n".join(lines) + "\n\nQatnashish uchun quyidagi tugmalardan foydalaning:",
        reply_markup=public_contests_kb(active_contests),
    )


@router.callback_query(F.data.startswith("join_random:"))
@module_guard("contest_module")
async def join_random_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    contest_id = int(callback.data.split(":")[1])
    contest = await session.get(Contest, contest_id)
    if contest is None or contest.status != ContestStatus.ACTIVE:
        await callback.answer("Bu konkurs endi faol emas.", show_alert=True)
        return

    is_new = await join_random_contest(session, contest_id, callback.from_user.id)
    text = (
        f"🎲 Siz '<b>{contest.title}</b>' konkursiga qo'shildingiz!\n\n"
        f"Sizning ID: <code>{callback.from_user.id}</code>\n\n"
        "G'oliblar tasodifiy tanlov orqali aniqlanadi va admin tomonidan e'lon qilinadi."
        if is_new else
        f"Siz allaqachon '<b>{contest.title}</b>' konkursida ishtirokchisiz.\n\n"
        f"Sizning ID: <code>{callback.from_user.id}</code>"
    )
    await callback.message.answer(text)
    await callback.answer()


@router.callback_query(F.data == "get_referral_link")
@module_guard("contest_module")
async def get_referral_link_callback(callback: CallbackQuery, **kwargs):
    await callback.message.answer(await _referral_link_text(callback))
    await callback.answer()


@router.message(F.text == "🏆 Reyting")
@module_guard("contest_module")
async def public_rating(message: Message, session: AsyncSession, **kwargs):
    # Ommaviy reyting - faqat ism-familiya ko'rsatiladi (username/nickname yo'q).
    # Kengaytirilgan (ism + nickname) versiya faqat admin panelida ko'rinadi.
    active = await get_active_referral_contest(session)
    if active is None:
        await message.answer("Hozircha faol konkurs yo'q.")
        return

    # Admin tomonidan qo'lda qo'shilgan ball ODATDAGI (include_admin_bonus=True,
    # standart qiymat) reytingga QO'SHILADI - ya'ni ball/o'rin haqiqatan
    # o'zgaradi. Lekin bu yerda (va boshqa hech qayerda) uning manbasi/sababi
    # alohida ko'rsatilmaydi - u oddiy referal ball bilan bir xil ko'rinadi,
    # shuning uchun admin bonusi bilinmaydi.
    own_stats = await get_user_stats(session, active, message.from_user.id)

    leaderboard = await get_leaderboard(session, active, limit=100)
    if not leaderboard:
        await message.answer(
            f"🏆 <b>{active.title}</b>\n\n"
            "Hali hech kim do'st taklif qilmagan. Birinchi bo'lib boshlang!"
        )
        return

    lines = [f"{i}. {v.full_name} — {count} ball" for i, (v, count) in enumerate(leaderboard, start=1)]
    text = f"🏆 <b>{active.title}</b> reytingi (Top {len(lines)})\n\n" + "\n".join(lines)

    if own_stats is None:
        text += (
            "\n\n📍 Siz hali reytingda emassiz - hali birorta ham tasdiqlangan "
            "taklifingiz yo'q. \"🔗 Do'stlarni taklif qilish\" tugmasidan havolangizni oling!"
        )
    else:
        rank, count = own_stats
        if rank > len(lines):
            text += f"\n\n📍 <b>Sizning o'rningiz: #{rank}</b> ({count} ball)"
        else:
            text += f"\n\n📍 <b>Siz #{rank} o'rindasiz!</b>"

    await message.answer(text)


@router.message(F.text == "🔗 Do'stlarni taklif qilish")
@module_guard("contest_module")
async def my_referral_link(message: Message, **kwargs):
    await message.answer(await _referral_link_text(message))


async def _referral_link_text(event: Message | CallbackQuery) -> str:
    # Hamma - hatto ro'yxatdan o'tmagan mehmon ham - taklif havolasiga ega
    # bo'lishi va konkursda qatnashishi mumkin (Visitor jadvali orqali kuzatiladi).
    bot_info = await event.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{event.from_user.id}"
    return (
        "🔗 <b>Sizning shaxsiy taklif havolangiz</b>\n\n"
        f"{link}\n\n"
        "Bu havola orqali kirgan har bir do'stingiz botni ishga tushirib, "
        "barcha majburiy kanallarga a'zo bo'lsagina konkurs reytingingizga "
        "qo'shiladi. Reytingni \"🏆 Reyting\" tugmasidan kuzatib boring!"
    )
