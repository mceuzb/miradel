from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User
from bot.keyboards.menus import menu_for_role

router = Router(name="common")


@router.callback_query(F.data == "check_subscription")
async def recheck_subscription(callback: CallbackQuery, db_user: User | None, session: AsyncSession, **kwargs):
    # Bu handlerga yetib kelgan bo'lsa - SubscriptionCheckMiddleware allaqachon
    # foydalanuvchi barcha kanallarga a'zo ekanini tasdiqlagan
    await callback.message.delete()
    if db_user:
        await callback.message.answer(
            "✅ Rahmat! Botdan foydalanishingiz mumkin.",
            reply_markup=await menu_for_role(session, db_user.role),
        )
    await callback.answer()
