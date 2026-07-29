from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import GroupStudent, Task, TaskSubmission, User, UserRole
from bot.middlewares.module_guard import module_guard
from bot.middlewares.role_check import require_role
from bot.utils.states import TaskSubmission as TaskSubmissionState

router = Router(name="student_tasks")


@router.message(F.text == "👤 Kabinetim")
@require_role(UserRole.STUDENT)
async def my_profile(message: Message, db_user: User, **kwargs):
    await message.answer(
        f"👤 Kabinetim\n\nIsm: {db_user.full_name}\nTelefon: {db_user.phone}"
    )


@router.message(F.text == "📝 Vazifalarim")
@require_role(UserRole.STUDENT)
@module_guard("task_module")
async def my_tasks(message: Message, session: AsyncSession, db_user: User, **kwargs):
    result = await session.execute(
        select(GroupStudent.group_id).where(GroupStudent.student_id == db_user.id)
    )
    group_ids = [row[0] for row in result.all()]
    if not group_ids:
        await message.answer("Siz hali biror guruhga biriktirilmagansiz.")
        return

    result = await session.execute(select(Task).where(Task.group_id.in_(group_ids)))
    tasks = result.scalars().all()
    if not tasks:
        await message.answer("Hozircha vazifalar yo'q.")
        return

    lines = []
    for t in tasks:
        deadline = t.deadline.strftime("%d.%m.%Y") if t.deadline else "belgilanmagan"
        lines.append(f"#{t.id} {t.title} (muddat: {deadline})")
    await message.answer(
        "📝 Vazifalaringiz:\n\n" + "\n".join(lines) +
        "\n\nTopshirish uchun: /submit <vazifa raqami>"
    )


@router.message(F.text.startswith("/submit"))
@require_role(UserRole.STUDENT)
@module_guard("task_module")
async def submit_task_start(message: Message, state: FSMContext, **kwargs):
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /submit <vazifa raqami>")
        return
    await state.update_data(task_id=int(parts[1]))
    await message.answer("Vazifa javobini matn yoki fayl ko'rinishida yuboring:")
    await state.set_state(TaskSubmissionState.waiting_content)


@router.message(TaskSubmissionState.waiting_content)
async def submit_task_content(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    data = await state.get_data()
    task = await session.get(Task, data["task_id"])
    if task is None:
        await message.answer("Vazifa topilmadi.")
        await state.clear()
        return

    file_id = None
    if message.document:
        file_id = message.document.file_id
    elif message.photo:
        file_id = message.photo[-1].file_id

    submission = TaskSubmission(
        task_id=task.id,
        student_id=db_user.id,
        content=message.text or message.caption,
        file_id=file_id,
    )
    session.add(submission)
    await session.commit()
    await state.clear()
    await message.answer("✅ Vazifangiz topshirildi. O'qituvchi tekshirib, baho qo'yadi.")

    creator = await session.get(User, task.created_by)
    if creator:
        try:
            await message.bot.send_message(
                creator.telegram_id,
                f"📥 {db_user.full_name} '{task.title}' vazifasini topshirdi.",
            )
        except Exception:
            pass
