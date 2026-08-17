from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Group, GroupEnrollmentStatus, User, UserRole, UserStatus
from bot.keyboards.admin_kb import ENROLLMENT_STATUS_LABELS, group_status_select_kb, groups_list_kb, teacher_select_kb
from bot.keyboards.course_kb import course_select_kb
from bot.middlewares.role_check import require_role
from bot.services.group_service import get_open_groups, get_students_without_group
from bot.utils.states import GroupCreation

router = Router(name="admin_groups")


@router.message(F.text == "👥 Guruhlar")
@require_role(UserRole.ADMIN)
async def list_groups(message: Message, session: AsyncSession, **kwargs):
    result = await session.execute(select(Group).where(Group.is_archived == False))  # noqa: E712
    groups = result.scalars().all()
    text = (
        "👥 Guruhlar ro'yxati - statusni o'zgartirish uchun guruh ustiga bosing:"
        if groups else "Hozircha guruhlar yo'q."
    )
    await message.answer(text, reply_markup=groups_list_kb(groups))


@router.callback_query(F.data == "new_group")
@require_role(UserRole.ADMIN)
async def new_group_start(callback: CallbackQuery, state: FSMContext, **kwargs):
    await callback.message.answer("Yangi guruh nomini kiriting:")
    await state.set_state(GroupCreation.waiting_name)
    await callback.answer()


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


@router.callback_query(F.data.startswith("assign_teacher:"))
@require_role(UserRole.ADMIN)
async def assign_teacher_start(callback: CallbackQuery, session: AsyncSession, **kwargs):
    group_id = int(callback.data.split(":")[1])
    result = await session.execute(
        select(User).where(User.role == UserRole.TEACHER, User.status == UserStatus.APPROVED)
    )
    teachers = result.scalars().all()
    if not teachers:
        await callback.answer("Hozircha tasdiqlangan o'qituvchi yo'q.", show_alert=True)
        return
    await callback.message.answer(
        "Qaysi o'qituvchini biriktiramiz?",
        reply_markup=teacher_select_kb(teachers, group_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_group_teacher:"))
@require_role(UserRole.ADMIN)
async def set_group_teacher(callback: CallbackQuery, session: AsyncSession, **kwargs):
    _, group_id_str, teacher_id_str = callback.data.split(":")
    group = await session.get(Group, int(group_id_str))
    teacher = await session.get(User, int(teacher_id_str))
    if group is None or teacher is None:
        await callback.answer("Topilmadi", show_alert=True)
        return

    group.teacher_id = teacher.id
    await session.commit()

    await callback.message.edit_text(f"✅ '{group.name}' guruhiga o'qituvchi biriktirildi: {teacher.full_name}")
    await callback.answer("Biriktirildi")


@router.callback_query(F.data == "broadcast_course_selection")
@require_role(UserRole.ADMIN)
async def broadcast_course_selection(callback: CallbackQuery, session: AsyncSession, **kwargs):
    groups = await get_open_groups(session)
    if not groups:
        await callback.answer("Hozircha ochiq (qabul faol) kurs yo'q.", show_alert=True)
        return

    students = await get_students_without_group(session)
    if not students:
        await callback.answer("Kursi tanlanmagan eski o'quvchi topilmadi - hammasi allaqachon biriktirilgan.", show_alert=True)
        return

    sent = 0
    for student in students:
        try:
            await callback.bot.send_message(
                student.telegram_id,
                "📚 Assalomu alaykum! Endi bizda kursingizni tanlash imkoniyati qo'shildi.\n\n"
                "Qaysi kursga yozilmoqchisiz?",
                reply_markup=course_select_kb(groups, callback_prefix="pick_course", include_skip=False),
            )
            sent += 1
        except Exception:
            continue

    await callback.answer(f"✅ {sent} ta o'quvchiga xabar yuborildi (jami: {len(students)} ta).", show_alert=True)


@router.callback_query(F.data.startswith("pick_course:"))
async def pick_course_callback(callback: CallbackQuery, session: AsyncSession, db_user, **kwargs):
    from bot.services.group_service import enroll_student

    if db_user is None:
        await callback.answer()
        return

    group_id = int(callback.data.split(":", 1)[1])
    group = await session.get(Group, group_id)
    if group is None:
        await callback.answer("Kurs topilmadi", show_alert=True)
        return

    await enroll_student(session, group_id, db_user.id)
    await callback.message.edit_text(f"✅ '{group.name}' kursiga yozildingiz!")
    await callback.answer()
