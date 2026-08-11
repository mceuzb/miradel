from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Broadcast, Group, User, UserRole, UserStatus
from bot.keyboards.menus import contact_request_kb, remove_kb
from bot.services.broadcast_service import record_click, save_lead
from bot.utils.states import BroadcastLeadCapture

router = Router(name="broadcast_lead")


@router.callback_query(F.data.startswith("broadcast_interest:"))
async def broadcast_interest_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    broadcast_id = int(callback.data.split(":")[1])
    broadcast = await session.get(Broadcast, broadcast_id)
    if broadcast is None:
        await callback.answer("Bu xabar endi mavjud emas.", show_alert=True)
        return

    await record_click(session, broadcast_id, callback.from_user.id)
    await state.update_data(broadcast_id=broadcast_id)
    await callback.message.answer(
        "Ismingizni kiriting:",
        reply_markup=remove_kb(),
    )
    await state.set_state(BroadcastLeadCapture.waiting_name)
    await callback.answer()


@router.message(BroadcastLeadCapture.waiting_name)
async def broadcast_lead_name(message: Message, state: FSMContext):
    full_name = (message.text or "").strip()
    if len(full_name) < 3:
        await message.answer("Iltimos, to'liq ism-familiyangizni kiriting:")
        return
    await state.update_data(full_name=full_name)
    await message.answer("Endi telefon raqamingizni yuboring:", reply_markup=contact_request_kb())
    await state.set_state(BroadcastLeadCapture.waiting_phone)


@router.message(BroadcastLeadCapture.waiting_phone, F.contact)
async def broadcast_lead_phone_contact(message: Message, state: FSMContext, session: AsyncSession):
    await _finish_lead(message, state, session, message.contact.phone_number)


@router.message(BroadcastLeadCapture.waiting_phone, F.text)
async def broadcast_lead_phone_text(message: Message, state: FSMContext, session: AsyncSession):
    phone = message.text.strip()
    if len(phone) < 7:
        await message.answer("Noto'g'ri format. Telefon raqamingizni yuboring (masalan +998901234567):")
        return
    await _finish_lead(message, state, session, phone)


async def _finish_lead(message: Message, state: FSMContext, session: AsyncSession, phone: str):
    data = await state.get_data()
    broadcast_id = data["broadcast_id"]
    full_name = data["full_name"]
    await state.clear()

    await save_lead(session, broadcast_id, message.from_user.id, full_name, phone)
    await message.answer(
        "✅ Rahmat! Ma'lumotlaringiz qabul qilindi - tez orada siz bilan bog'lanamiz.",
        reply_markup=remove_kb(),
    )

    broadcast = await session.get(Broadcast, broadcast_id)
    course_line = ""
    if broadcast and broadcast.group_id:
        group = await session.get(Group, broadcast.group_id)
        if group is not None:
            course_line = f"Kurs: {group.name}\n"

    result = await session.execute(
        select(User).where(User.role == UserRole.ADMIN, User.status == UserStatus.APPROVED)
    )
    admins = result.scalars().all()
    text = (
        f"📚 Ommaviy xabar (#{broadcast_id}) bo'yicha yangi qiziqqan!\n\n"
        f"Ism: {full_name}\n"
        f"Telefon: {phone}\n"
        f"{course_line}"
        f"Telegram ID: {message.from_user.id}"
    )
    for admin in admins:
        try:
            await message.bot.send_message(admin.telegram_id, text)
        except Exception:
            continue
