import asyncio

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Group, User, UserRole
from bot.keyboards.admin_kb import broadcast_confirm_kb, broadcast_stats_kb, broadcasts_list_kb
from bot.keyboards.course_kb import course_select_kb
from bot.middlewares.role_check import require_role
from bot.services.broadcast_service import (
    create_broadcast, get_all_broadcasts, get_broadcast, get_leads, get_stats, run_broadcast,
)
from bot.services.export_service import build_leads_excel
from bot.utils.states import BroadcastCreation

router = Router(name="admin_broadcast")


@router.message(F.text == "📢 Ommaviy xabar")
@require_role(UserRole.ADMIN)
async def list_broadcasts(message: Message, session: AsyncSession, **kwargs):
    broadcasts = await get_all_broadcasts(session)
    text = "📢 Ommaviy xabarlar" if broadcasts else "📢 Hozircha ommaviy xabarlar yo'q."
    await message.answer(text, reply_markup=broadcasts_list_kb(broadcasts))


@router.callback_query(F.data == "new_broadcast")
@require_role(UserRole.ADMIN)
async def new_broadcast_start(callback: CallbackQuery, state: FSMContext, **kwargs):
    await callback.message.answer(
        "Ommaviy xabar matnini kiriting (masalan, yangi kurs haqida e'lon):"
    )
    await state.set_state(BroadcastCreation.waiting_text)
    await callback.answer()


@router.message(BroadcastCreation.waiting_text)
async def broadcast_text_entered(message: Message, state: FSMContext, session: AsyncSession):
    await state.update_data(text=message.text)

    result = await session.execute(select(Group).where(Group.is_archived == False))  # noqa: E712
    groups = result.scalars().all()
    if not groups:
        await state.update_data(group_id=None)
        await _show_preview(message, state)
        return

    await message.answer(
        "Xabar qaysi kursga tegishli? (tugma ostida shu kurs bo'ladi)",
        reply_markup=course_select_kb(groups, callback_prefix="broadcast_group", include_skip=True),
    )
    await state.set_state(BroadcastCreation.waiting_group)


@router.callback_query(BroadcastCreation.waiting_group, F.data.startswith("broadcast_group:"))
async def broadcast_group_selected(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":", 1)[1]
    group_id = None if value == "skip" else int(value)
    await state.update_data(group_id=group_id)
    await _show_preview(callback.message, state)
    await callback.answer()


async def _show_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    await message.answer(
        "📋 Xabar matni shunday ko'rinishda yuboriladi:\n\n"
        f"{data['text']}\n\n"
        "Yuborishni tasdiqlaysizmi?",
        reply_markup=broadcast_confirm_kb(),
    )
    await state.set_state(BroadcastCreation.waiting_confirm)


@router.callback_query(BroadcastCreation.waiting_confirm, F.data == "broadcast_cancel")
async def broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Bekor qilindi.")
    await callback.answer()


@router.callback_query(BroadcastCreation.waiting_confirm, F.data == "broadcast_confirm_send")
async def broadcast_confirm_send(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User):
    data = await state.get_data()
    await state.clear()

    broadcast = await create_broadcast(session, db_user.id, data["text"], data.get("group_id"))
    await callback.message.edit_text(
        "🚀 Yuborish boshlandi (har soniyada 5 tadan, flood-limitga tortilmaslik uchun).\n"
        "Tugagach, sizga alohida xabar beraman."
    )
    asyncio.create_task(run_broadcast(callback.bot, broadcast.id, callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast_stats:"))
@require_role(UserRole.ADMIN)
async def broadcast_stats_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    broadcast_id = int(callback.data.split(":")[1])
    broadcast = await get_broadcast(session, broadcast_id)
    if broadcast is None:
        await callback.answer("Topilmadi", show_alert=True)
        return

    stats = await get_stats(session, broadcast_id)
    status = "⏳ Hali yuborilmoqda..." if stats["is_sending"] else "✅ Yuborish yakunlangan"
    text = (
        f"📊 <b>#{broadcast.id} statistikasi</b>\n\n"
        f"{status}\n\n"
        f"🎯 Nechta odamga mo'ljallangan: {stats['targeted']}\n"
        f"📨 Nechtasiga yetib bordi: {stats['sent']}\n"
        f"🚫 Yetib bormadi (bloklagan/o'chirgan): {stats['failed']}\n"
        f"👀 Tugmani bosib qiziqqanlar: {stats['clicked']}\n"
        f"✅ Ism/telefon qoldirganlar: {stats['leads']}\n\n"
        "<i>Eslatma: Telegram bot API orqali kim xabarni haqiqatan o'qiganini "
        "bilib bo'lmaydi - shuning uchun 'qiziqqanlar' ko'rsatkichi tugmani "
        "bosganlar soniga asoslangan.</i>"
    )
    await callback.message.answer(text, reply_markup=broadcast_stats_kb(broadcast_id))
    await callback.answer()


@router.callback_query(F.data.startswith("broadcast_export:"))
@require_role(UserRole.ADMIN)
async def broadcast_export_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    broadcast_id = int(callback.data.split(":")[1])
    leads = await get_leads(session, broadcast_id)
    if not leads:
        await callback.answer("Hali hech kim ism/telefon qoldirmagan.", show_alert=True)
        return

    excel_bytes = build_leads_excel(leads)
    await callback.message.answer_document(
        BufferedInputFile(excel_bytes, filename=f"broadcast_{broadcast_id}_qiziqqanlar.xlsx"),
        caption=f"📥 #{broadcast_id} ommaviy xabar bo'yicha qiziqqanlar ({len(leads)} ta)",
    )
    await callback.answer()
