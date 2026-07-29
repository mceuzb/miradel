from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Group, GroupStudent, Task, User, UserRole
from bot.middlewares.module_guard import module_guard
from bot.middlewares.role_check import require_role
from bot.utils.states import TaskCreation

router = Router(name="teacher_tasks")


@router.message(F.text == "📝 Vazifa berish")
@require_role(UserRole.TEACHER)
@module_guard("task_module")
async def new_task_start(message: Message, state: FSMContext, session: AsyncSession, db_user: User, **kwargs):
    result = await session.execute(select(Group).where(Group.teacher_id == db_user.id))
    groups = result.scalars().all()
    if not groups:
        await message.answer("Sizga biriktirilgan guruh yo'q.")
        return
    await state.update_data(group_id=groups[0].id)  # MVP: birinchi guruhga beriladi
    await message.answer(f"'{groups[0].name}' guruhi uchun vazifa nomini kiriting:")
    await state.set_state(TaskCreation.waiting_title)


@router.message(TaskCreation.waiting_title)
async def task_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await message.answer("Vazifa tavsifini kiriting (yoki '-' agar kerak bo'lmasa):")
    await state.set_state(TaskCreation.waiting_description)


@router.message(TaskCreation.waiting_description)
async def task_description(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    data = await state.get_data()
    description = None if message.text.strip() == "-" else message.text.strip()
    task = Task(
        group_id=data["group_id"],
        title=data["title"],
        description=description,
        created_by=db_user.id,
    )
    session.add(task)
    await session.commit()
    await state.clear()
    await message.answer(f"✅ '{task.title}' vazifasi guruhga yuborildi.")

    # 5-bo'lim: yangi vazifa berilganda o'quvchilarga avtomatik xabar
    result = await session.execute(
        select(GroupStudent).where(GroupStudent.group_id == data["group_id"])
    )
    memberships = result.scalars().all()
    for m in memberships:
        student = await session.get(User, m.student_id)
        if student:
            try:
                await message.bot.send_message(
                    student.telegram_id,
                    f"📝 Yangi vazifa: {task.title}\n{description or ''}",
                )
            except Exception:
                continue
