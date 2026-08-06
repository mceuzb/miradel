from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Contest, ContestParticipant, ContestStatus, ContestType, UserRole
from bot.keyboards.admin_kb import contest_type_select_kb, contests_kb
from bot.middlewares.role_check import require_role
from bot.services.contest_service import (
    create_contest, finish_contest, finish_random_contest, get_all_contests,
    get_contest_participants, get_contest_results,
)
from bot.services.export_service import build_participants_excel
from bot.services.referral_service import get_leaderboard
from bot.utils.states import ContestCreation, RandomContestFinish

router = Router(name="admin_contests")

STATUS_LABELS = {
    ContestStatus.DRAFT: "Qoralama",
    ContestStatus.ACTIVE: "Faol",
    ContestStatus.FINISHED: "Yakunlangan",
}
TYPE_LABELS = {
    ContestType.REFERRAL: "🏆 Referal",
    ContestType.RANDOM: "🎲 Random",
}


async def _render_contests_message(message: Message, session: AsyncSession):
    contests = await get_all_contests(session)
    if not contests:
        text = "🎁 Konkurslar\n\nHozircha konkurslar yo'q. Yangi konkurs yaratish uchun pastdagi tugmani bosing."
    else:
        lines = [
            f"#{c.id} [{TYPE_LABELS[c.contest_type]}] {c.title} — {STATUS_LABELS.get(c.status, c.status.value)}"
            for c in contests
        ]
        text = "🎁 Konkurslar\n\n" + "\n".join(lines)
    await message.answer(text, reply_markup=contests_kb(contests))


def _format_results(contest: Contest, results: list[tuple]) -> str:
    if not results:
        return f"🏁 '{contest.title}' yakunlandi.\n\nHech kim shart bajarmadi, g'oliblar aniqlanmadi."
    lines = []
    for r, v in results:
        count_part = f" — {r.referral_count} ta" if contest.contest_type == ContestType.REFERRAL else ""
        if v is None:
            lines.append(f"{r.rank}-o'rin: (telegram_id: {r.winner_telegram_id}){count_part} — 🎁 {r.prize}")
            continue
        username = f"@{v.username}" if v.username else "(username yo'q)"
        lines.append(f"{r.rank}-o'rin: {v.full_name} {username}{count_part} — 🎁 {r.prize}")
    return f"🏁 '{contest.title}' g'oliblari ({len(results)} ta):\n\n" + "\n".join(lines)


@router.message(F.text == "🎛 Konkurslarni boshqarish")
@require_role(UserRole.ADMIN)
async def list_contests(message: Message, session: AsyncSession, **kwargs):
    await _render_contests_message(message, session)


@router.callback_query(F.data == "new_contest")
@require_role(UserRole.ADMIN)
async def new_contest_start(callback: CallbackQuery, state: FSMContext, **kwargs):
    await callback.message.answer("Konkurs turini tanlang:", reply_markup=contest_type_select_kb())
    await state.set_state(ContestCreation.waiting_type)
    await callback.answer()


@router.callback_query(ContestCreation.waiting_type, F.data.startswith("contest_type:"))
async def contest_type_selected(callback: CallbackQuery, state: FSMContext):
    contest_type = ContestType(callback.data.split(":", 1)[1])
    await state.update_data(contest_type=contest_type.value)
    await callback.message.answer("Yangi konkurs nomini kiriting:")
    await state.set_state(ContestCreation.waiting_title)
    await callback.answer()


@router.message(ContestCreation.waiting_title)
async def contest_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Konkurs tugash sanasini kiriting (KK.OO.YYYY, masalan: 31.08.2026):")
    await state.set_state(ContestCreation.waiting_end_date)


@router.message(ContestCreation.waiting_end_date)
async def contest_end_date(message: Message, state: FSMContext):
    try:
        end_date = datetime.strptime(message.text.strip(), "%d.%m.%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        await message.answer("Noto'g'ri format. Masalan: 31.08.2026 ko'rinishida kiriting:")
        return
    await state.update_data(end_date=end_date.isoformat())
    await message.answer("Nechta o'ringa sovg'a beriladi? (masalan: 3)")
    await state.set_state(ContestCreation.waiting_winners_count)


@router.message(ContestCreation.waiting_winners_count)
async def contest_winners_count(message: Message, state: FSMContext):
    raw = message.text.strip()
    if not raw.isdigit() or int(raw) < 1:
        await message.answer("Iltimos, musbat butun son kiriting (masalan: 3):")
        return
    winners_count = int(raw)
    await state.update_data(winners_count=winners_count, prizes=[], current_rank=1)
    await message.answer("1-o'rin uchun sovg'ani kiriting (masalan: Xiaomi Redmi Note):")
    await state.set_state(ContestCreation.waiting_prize)


@router.message(ContestCreation.waiting_prize)
async def contest_prize(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    prizes: list[dict] = data["prizes"]
    current_rank: int = data["current_rank"]
    winners_count: int = data["winners_count"]

    prizes.append({"rank": current_rank, "prize": message.text.strip()})

    if current_rank < winners_count:
        await state.update_data(prizes=prizes, current_rank=current_rank + 1)
        await message.answer(f"{current_rank + 1}-o'rin uchun sovg'ani kiriting:")
        return

    end_date = datetime.fromisoformat(data["end_date"])
    contest_type = ContestType(data["contest_type"])
    contest = await create_contest(session, data["title"], end_date, prizes, contest_type)
    await state.clear()

    prize_lines = "\n".join(f"{p['rank']}-o'rin: {p['prize']}" for p in prizes)
    await message.answer(
        f"✅ '{contest.title}' konkursi ({TYPE_LABELS[contest_type]}) ishga tushirildi!\n\n"
        f"Tugash sanasi: {contest.end_date.strftime('%d.%m.%Y')}\n\n"
        f"Sovg'alar:\n{prize_lines}"
    )


@router.callback_query(F.data.startswith("contest_rating:"))
@require_role(UserRole.ADMIN)
async def contest_rating_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    contest_id = int(callback.data.split(":")[1])
    contest = await session.get(Contest, contest_id)
    if contest is None:
        await callback.answer("Konkurs topilmadi", show_alert=True)
        return

    leaderboard = await get_leaderboard(session, contest, limit=100)
    if not leaderboard:
        await callback.message.answer("Hali hech kim referal orqali odam taklif qilmagan.")
        await callback.answer()
        return

    lines = []
    for i, (visitor, count) in enumerate(leaderboard, start=1):
        username = f"@{visitor.username}" if visitor.username else "(username yo'q)"
        lines.append(f"{i}. {visitor.full_name} {username} — {count} ta")
    await callback.message.answer(
        f"📊 '{contest.title}' reytingi — Top {len(lines)} (faqat admin ko'rinishi)\n\n" + "\n".join(lines)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("contest_participants_count:"))
@require_role(UserRole.ADMIN)
async def contest_participants_count_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    contest_id = int(callback.data.split(":")[1])
    participants = await get_contest_participants(session, contest_id)
    await callback.answer(f"👥 Hozircha {len(participants)} ta ishtirokchi qo'shilgan.", show_alert=True)


@router.callback_query(F.data.startswith("finish_contest:"))
@require_role(UserRole.ADMIN)
async def finish_contest_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    contest_id = int(callback.data.split(":")[1])
    contest = await finish_contest(session, contest_id)
    if contest is None:
        await callback.answer("Konkurs topilmadi yoki allaqachon yakunlangan", show_alert=True)
        return

    results = await get_contest_results(session, contest_id)
    await callback.message.answer(_format_results(contest, results))
    await callback.answer("Konkurs yakunlandi")
    await _render_contests_message(callback.message, session)


@router.callback_query(F.data.startswith("finish_random_contest:"))
@require_role(UserRole.ADMIN)
async def finish_random_contest_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession, **kwargs):
    contest_id = int(callback.data.split(":")[1])
    contest = await session.get(Contest, contest_id)
    if contest is None or contest.status != ContestStatus.ACTIVE or contest.contest_type != ContestType.RANDOM:
        await callback.answer("Konkurs topilmadi yoki mos emas", show_alert=True)
        return

    places = contest.prizes.get("places", [])
    if not places:
        await callback.answer("Bu konkursda sovg'alar ro'yxati yo'q", show_alert=True)
        return

    await state.update_data(contest_id=contest_id, winners=[], current_rank=1, winners_count=len(places))
    await callback.message.answer(
        f"🎲 '{contest.title}' uchun g'oliblarni e'lon qilish.\n\n"
        "1-o'rin g'olibining Telegram ID raqamini yuboring "
        "(ishtirokchilar ro'yxatini avval Excel orqali yuklab olib, u yerdan ID'ni ko'rishingiz mumkin):"
    )
    await state.set_state(RandomContestFinish.waiting_winner_id)
    await callback.answer()


@router.message(RandomContestFinish.waiting_winner_id)
async def random_contest_winner_id(message: Message, state: FSMContext, session: AsyncSession):
    raw = message.text.strip()
    if not raw.lstrip("-").isdigit():
        await message.answer("Noto'g'ri format. Faqat Telegram ID (raqam) yuboring:")
        return
    telegram_id = int(raw)

    data = await state.get_data()
    contest_id = data["contest_id"]

    exists = await session.execute(
        select(ContestParticipant).where(
            ContestParticipant.contest_id == contest_id, ContestParticipant.telegram_id == telegram_id,
        )
    )
    if exists.scalar_one_or_none() is None:
        await message.answer(
            "⚠️ Bu ID ishtirokchilar ro'yxatida topilmadi. Qaytadan tekshirib, to'g'ri ID yuboring:"
        )
        return

    winners: list[list[int]] = data["winners"]
    current_rank: int = data["current_rank"]
    winners_count: int = data["winners_count"]
    winners.append([current_rank, telegram_id])

    if current_rank < winners_count:
        await state.update_data(winners=winners, current_rank=current_rank + 1)
        await message.answer(f"{current_rank + 1}-o'rin g'olibining Telegram ID raqamini yuboring:")
        return

    contest = await finish_random_contest(session, contest_id, [(r, t) for r, t in winners])
    await state.clear()
    if contest is None:
        await message.answer("Xatolik: konkurs topilmadi yoki allaqachon yakunlangan.")
        return

    results = await get_contest_results(session, contest_id)
    await message.answer(_format_results(contest, results))

    for r, v in results:
        try:
            await message.bot.send_message(
                r.winner_telegram_id,
                f"🎉 Tabriklaymiz! Siz '<b>{contest.title}</b>' konkursida "
                f"<b>{r.rank}-o'rinni</b> egalladingiz!\n🎁 Sovg'a: {r.prize}",
            )
        except Exception:
            continue

    await _render_contests_message(message, session)


@router.callback_query(F.data.startswith("contest_results:"))
@require_role(UserRole.ADMIN)
async def contest_results_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    contest_id = int(callback.data.split(":")[1])
    contest = await session.get(Contest, contest_id)
    if contest is None:
        await callback.answer("Konkurs topilmadi", show_alert=True)
        return
    results = await get_contest_results(session, contest_id)
    await callback.message.answer(_format_results(contest, results))
    await callback.answer()


@router.callback_query(F.data.startswith("contest_export:"))
@require_role(UserRole.ADMIN)
async def contest_export_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    contest_id = int(callback.data.split(":")[1])
    contest = await session.get(Contest, contest_id)
    if contest is None:
        await callback.answer("Konkurs topilmadi", show_alert=True)
        return

    if contest.contest_type == ContestType.RANDOM:
        leaderboard = await get_contest_participants(session, contest_id)
        empty_text = "Hali hech kim konkursga qo'shilmagan."
    else:
        leaderboard = await get_leaderboard(session, contest, limit=None)
        empty_text = "Hali hech kim referal orqali odam taklif qilmagan."

    if not leaderboard:
        await callback.answer(empty_text, show_alert=True)
        return

    excel_bytes = build_participants_excel(contest, leaderboard)
    safe_title = "".join(ch if ch.isalnum() else "_" for ch in contest.title)
    filename = f"{safe_title}_ishtirokchilar.xlsx"

    await callback.message.answer_document(
        BufferedInputFile(excel_bytes, filename=filename),
        caption=f"📥 '{contest.title}' — barcha ishtirokchilar ({len(leaderboard)} ta)",
    )
    await callback.answer()
