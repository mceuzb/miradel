from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import UserRole
from bot.middlewares.role_check import require_role
from bot.services.user_service import remove_student, search_approved_students
from bot.utils.states import RemoveStudent

router = Router(name="admin_remove_student")


def _remove_confirm_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Ha, o'chirish", callback_data=f"remove_student:{user_id}"),
    ]])


@router.message(F.text == "🗑 O'quvchini o'chirish")
@require_role(UserRole.ADMIN)
async def remove_student_start(message: Message, state: FSMContext, **kwargs):
    await message.answer(
        "O'chirmoqchi bo'lgan o'quvchining ism yoki familiyasidan bir qismini yozing:\n\n"
        "ℹ️ Bu asosan sinov paytida xato tasdiqlangan (haqiqiy o'quvchi bo'lmagan) "
        "hisoblarni tozalash uchun. O'chirilgan odam botga kirsa \"o'quvchilar "
        "bazasidan topilmadingiz\" xabarini ko'radi."
    )
    await state.set_state(RemoveStudent.waiting_query)


@router.message(RemoveStudent.waiting_query)
async def remove_student_search(message: Message, state: FSMContext, session: AsyncSession, **kwargs):
    query = (message.text or "").strip()
    if len(query) < 2:
        await message.answer("Kamida 2 belgi kiriting:")
        return
    await state.clear()

    students = await search_approved_students(session, query)
    if not students:
        await message.answer("Hech kim topilmadi.")
        return

    for student in students:
        login_line = f"\nLogin: {student.login}" if student.login else ""
        await message.answer(
            f"👤 {student.full_name}{login_line}",
            reply_markup=_remove_confirm_kb(student.id),
        )


@router.callback_query(F.data.startswith("remove_student:"))
@require_role(UserRole.ADMIN)
async def remove_student_confirm(callback: CallbackQuery, session: AsyncSession, **kwargs):
    user_id = int(callback.data.split(":")[1])
    user = await remove_student(session, user_id)
    if user is None:
        await callback.answer("Foydalanuvchi topilmadi", show_alert=True)
        return

    await callback.message.edit_text(f"🗑 {user.full_name} o'chirildi.")
    await callback.answer("O'chirildi")

    if user.telegram_id:
        try:
            from bot.middlewares.access_control import REMOVED_TEXT
            await callback.bot.send_message(user.telegram_id, REMOVED_TEXT)
        except Exception:
            pass
