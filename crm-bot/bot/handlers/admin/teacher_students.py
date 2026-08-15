from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Group, GroupStudent, User, UserRole
from bot.keyboards.admin_kb import teacher_student_approval_kb
from bot.middlewares.role_check import require_role
from bot.services.teacher_student_service import get_teacher_added_pending
from bot.services.user_service import approve_user, reject_user

router = Router(name="admin_teacher_students")


@router.message(F.text == "👩‍🎓 O'qituvchi qo'shganlar")
@require_role(UserRole.ADMIN)
async def list_teacher_added(message: Message, session: AsyncSession, **kwargs):
    pending = await get_teacher_added_pending(session)
    if not pending:
        await message.answer("Hozircha o'qituvchilar qo'shgan yangi o'quvchilar yo'q.")
        return
    for user in pending:
        teacher_line = ""
        if user.added_by_teacher_id:
            teacher = await session.get(User, user.added_by_teacher_id)
            if teacher is not None:
                teacher_line = f"O'qituvchi: {teacher.full_name}\n"

        group_line = ""
        gs = await session.execute(
            select(Group).join(GroupStudent, GroupStudent.group_id == Group.id)
            .where(GroupStudent.student_id == user.id)
        )
        group = gs.scalars().first()
        if group is not None:
            group_line = f"Guruh: {group.name}\n"

        text = (
            f"Ism: {user.full_name}\n"
            f"Login: {user.login}\n"
            f"{teacher_line}"
            f"{group_line}"
        )
        await message.answer(text, reply_markup=teacher_student_approval_kb(user.id))


@router.callback_query(F.data.startswith("approve_ts:"))
@require_role(UserRole.ADMIN)
async def approve_ts_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    user_id = int(callback.data.split(":")[1])
    user = await approve_user(session, user_id, UserRole.STUDENT)
    if user is None:
        await callback.answer("Foydalanuvchi topilmadi", show_alert=True)
        return

    await callback.message.edit_text(callback.message.text + "\n\n✅ Tasdiqlandi")
    await callback.answer("Tasdiqlandi")
    if user.telegram_id:
        try:
            await callback.bot.send_message(
                user.telegram_id,
                f"🎉 Tabriklaymiz, {user.full_name}! Hisobingiz tasdiqlandi.\n"
                f"Endi shaxsiy kabinetingiz va Alpino'dan to'liq foydalanishingiz mumkin. /start bosing.",
            )
        except Exception:
            pass


@router.callback_query(F.data.startswith("reject_ts:"))
@require_role(UserRole.ADMIN)
async def reject_ts_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    user_id = int(callback.data.split(":")[1])
    user = await reject_user(session, user_id)
    if user is None:
        await callback.answer("Foydalanuvchi topilmadi", show_alert=True)
        return

    await callback.message.edit_text(callback.message.text + "\n\n❌ Rad etildi")
    await callback.answer("Rad etildi")
