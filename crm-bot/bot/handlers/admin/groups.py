from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Group, GroupEnrollmentStatus, UserRole
from bot.keyboards.admin_kb import ENROLLMENT_STATUS_LABELS, group_status_select_kb, groups_list_kb
from bot.middlewares.role_check import require_role
from bot.utils.states import GroupCreation

router = Router(name="admin_groups")


@router.message(F.text == "👥 Guruhlar")
@require_role(UserRole.ADMIN)
async def list_groups(message: Message, session: AsyncSession, **kwargs):
    result = await session.execute(select(Group).where(Group.is_archived == False))  # noqa: E712
    groups = result.scalars().all()
    if not groups:
        await message.answer("Hozircha guruhlar yo'q.\n\nYangi guruh yaratish uchun /new_group buyrug'ini yuboring.")
        return
    await message.answer(
        "👥 Guruhlar ro'yxati - statusni o'zgartirish uchun guruh ustiga bosing:\n\n"
        "Yangi guruh yaratish uchun /new_group buyrug'ini yuboring.",
        reply_markup=groups_list_kb(groups),
    )


@router.message(F.text == "/new_group")
@require_role(UserRole.ADMIN)
async def new_group_start(message: Message, state: FSMContext, **kwargs):
    await message.answer("Yangi guruh nomini kiriting:")
    await state.set_state(GroupCreation.waiting_name)


@router.message(GroupCreation.waiting_name)
async def new_group_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Fan/yo'nalishini kiriting:")
    await state.set_state(GroupCreation.waiting_subject)


@router.message(GroupCreation.waiting_subject)
async def new_group_subject(message: Message, state: FSMContext):
    await state.update_data(subject=message.text.strip())
    await message.answer(
        "Qabul holatini tanlang:",
        reply_markup=group_status_select_kb("new_group_status"),
    )
    await state.set_state(GroupCreation.waiting_status)


@router.callback_query(GroupCreation.waiting_status, F.data.startswith("new_group_status:"))
async def new_group_finish(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    status_value = callback.data.split(":", 1)[1]
    status = GroupEnrollmentStatus(status_value)
    data = await state.get_data()

    group = Group(name=data["name"], subject=data["subject"], enrollment_status=status)
    session.add(group)
    await session.commit()
    await state.clear()

    await callback.message.edit_text(
        f"✅ '{group.name}' guruhi yaratildi.\n"
        f"Status: {ENROLLMENT_STATUS_LABELS[status]}\n\n"
        "Endi unga o'qituvchi biriktirishingiz mumkin."
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_group_status:"))
@require_role(UserRole.ADMIN)
async def edit_group_status_start(callback: CallbackQuery, **kwargs):
    group_id = int(callback.data.split(":")[1])
    await callback.message.answer(
        "Yangi qabul holatini tanlang:",
        reply_markup=group_status_select_kb(f"set_group_status:{group_id}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_group_status:"))
@require_role(UserRole.ADMIN)
async def set_group_status(callback: CallbackQuery, session: AsyncSession, **kwargs):
    _, group_id_str, status_value = callback.data.split(":")
    group = await session.get(Group, int(group_id_str))
    if group is None:
        await callback.answer("Guruh topilmadi", show_alert=True)
        return

    group.enrollment_status = GroupEnrollmentStatus(status_value)
    await session.commit()

    await callback.message.edit_text(
        f"✅ '{group.name}' guruhi statusi yangilandi: {ENROLLMENT_STATUS_LABELS[group.enrollment_status]}"
    )
    await callback.answer("Yangilandi")
