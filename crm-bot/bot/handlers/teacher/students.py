from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Group, User, UserRole, UserStatus
from bot.keyboards.admin_kb import teacher_student_approval_kb
from bot.keyboards.course_kb import course_select_kb
from bot.middlewares.role_check import require_role
from bot.services.teacher_student_service import create_teacher_student
from bot.utils.states import TeacherAddStudent

router = Router(name="teacher_students")


@router.message(F.text == "➕ O'quvchi qo'shish")
@require_role(UserRole.TEACHER)
async def add_student_start(message: Message, state: FSMContext, **kwargs):
    await message.answer(
        "Yangi o'quvchining to'liq ism-familiyasini kiriting:\n\n"
        "ℹ️ O'quvchida Telegram bo'lishi shart emas - tizim avtomatik login va "
        "parol yaratadi, buni siz o'quvchiga (yoki ota-onasiga) berasiz.",
    )
    await state.set_state(TeacherAddStudent.waiting_full_name)


@router.message(TeacherAddStudent.waiting_full_name)
async def add_student_name(message: Message, state: FSMContext, session: AsyncSession, db_user: User, **kwargs):
    full_name = (message.text or "").strip()
    if len(full_name) < 3:
        await message.answer("Iltimos, to'liq ism-familiyani kiriting (kamida 3 belgi):")
        return
    await state.update_data(full_name=full_name)

    result = await session.execute(select(Group).where(Group.teacher_id == db_user.id, Group.is_archived == False))  # noqa: E712
    groups = list(result.scalars().all())
    if not groups:
        await _finish(message, state, session, db_user, group_id=None)
        return

    await message.answer(
        "Qaysi guruhga qo'shamiz?",
        reply_markup=course_select_kb(groups, callback_prefix="ts_group"),
    )
    await state.set_state(TeacherAddStudent.waiting_group)


@router.callback_query(TeacherAddStudent.waiting_group, F.data.startswith("ts_group:"))
async def add_student_group(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User, **kwargs):
    value = callback.data.split(":", 1)[1]
    group_id = None if value == "skip" else int(value)
    await callback.message.edit_reply_markup(reply_markup=None)
    await _finish(callback.message, state, session, db_user, group_id=group_id, answer_target=callback)


async def _finish(
    message: Message, state: FSMContext, session: AsyncSession, teacher: User,
    group_id: int | None, answer_target: CallbackQuery | None = None,
):
    data = await state.get_data()
    full_name = data["full_name"]
    await state.clear()

    user, password = await create_teacher_student(session, teacher, full_name, group_id)

    text = (
        f"✅ O'quvchi qo'shildi: <b>{user.full_name}</b>\n\n"
        f"🔑 Login: <code>{user.login}</code>\n"
        f"🔐 Parol: <code>{password}</code>\n\n"
        f"Bu login/parolni o'quvchi (yoki ota-onasi)ga bering - Telegram'ni "
        f"ochib, botga kirib, \"🔑 Login orqali kirish\" tugmasi orqali "
        f"shaxsiy kabinetiga kira oladi.\n\n"
        f"⏳ Admin tasdiqlagach, Alpino'dan ham foydalana oladi."
    )
    await message.answer(text)
    if answer_target is not None:
        await answer_target.answer()

    await _notify_admins(message.bot, session, user, teacher)


async def _notify_admins(bot, session: AsyncSession, user: User, teacher: User):
    result = await session.execute(
        select(User).where(User.role == UserRole.ADMIN, User.status == UserStatus.APPROVED)
    )
    admins = result.scalars().all()
    text = (
        f"👩‍🎓 O'qituvchi yangi o'quvchi qo'shdi!\n\n"
        f"O'quvchi: {user.full_name}\n"
        f"Login: {user.login}\n"
        f"O'qituvchi: {teacher.full_name}"
    )
    for admin in admins:
        if not admin.telegram_id:
            continue
        try:
            await bot.send_message(admin.telegram_id, text, reply_markup=teacher_student_approval_kb(user.id))
        except Exception:
            continue
