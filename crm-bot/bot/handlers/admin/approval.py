from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, UserRole
from bot.keyboards.admin_kb import approval_kb
from bot.middlewares.role_check import require_role
from bot.services.user_service import approve_user, get_pending_users, reject_user

router = Router(name="admin_approval")


@router.message(F.text == "🆕 Yangi so'rovlar")
@require_role(UserRole.ADMIN)
async def list_pending(message: Message, session: AsyncSession, **kwargs):
    pending = await get_pending_users(session)
    if not pending:
        await message.answer("Hozircha yangi so'rovlar yo'q.")
        return
    for user in pending:
        text = f"Ism: {user.full_name}\nTelefon: {user.phone}\nTelegram ID: {user.telegram_id}"
        await message.answer(text, reply_markup=approval_kb(user.id))


@router.callback_query(F.data.startswith("approve:"))
@require_role(UserRole.ADMIN)
async def approve_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    _, role_str, user_id_str = callback.data.split(":")
    role = UserRole.TEACHER if role_str == "teacher" else UserRole.STUDENT
    user = await approve_user(session, int(user_id_str), role)
    if user is None:
        await callback.answer("Foydalanuvchi topilmadi", show_alert=True)
        return

    await callback.message.edit_text(
        callback.message.text + f"\n\n✅ Tasdiqlandi ({role.value})"
    )
    await callback.answer("Tasdiqlandi")
    try:
        await callback.bot.send_message(
            user.telegram_id,
            f"🎉 Tabriklaymiz, {user.full_name}! Arizangiz tasdiqlandi.\nEndi botdan to'liq foydalanishingiz mumkin. /start bosing.",
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("reject:"))
@require_role(UserRole.ADMIN)
async def reject_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    user_id = int(callback.data.split(":")[1])
    user = await reject_user(session, user_id)
    if user is None:
        await callback.answer("Foydalanuvchi topilmadi", show_alert=True)
        return

    await callback.message.edit_text(callback.message.text + "\n\n❌ Rad etildi")
    await callback.answer("Rad etildi")
    try:
        await callback.bot.send_message(
            user.telegram_id,
            "❌ Afsuski, arizangiz rad etildi. Qayta murojaat qilish uchun /start bosing.",
        )
    except Exception:
        pass
