from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, UserRole
from bot.keyboards.admin_kb import modules_kb
from bot.middlewares.role_check import require_role
from bot.services.module_service import get_all_modules, toggle_module

router = Router(name="admin_modules")


@router.message(F.text == "⚙️ Modullar")
@require_role(UserRole.ADMIN)
async def show_modules(message: Message, session: AsyncSession, **kwargs):
    modules = await get_all_modules(session)
    await message.answer(
        "⚙️ Modullarni boshqarish\n\nYoqish/o'chirish uchun bosing:",
        reply_markup=modules_kb(modules),
    )


@router.callback_query(F.data.startswith("toggle_module:"))
@require_role(UserRole.ADMIN)
async def toggle_module_callback(callback: CallbackQuery, session: AsyncSession, db_user: User, **kwargs):
    module_key = callback.data.split(":", 1)[1]
    await toggle_module(session, module_key, db_user.id)
    modules = await get_all_modules(session)
    await callback.message.edit_reply_markup(reply_markup=modules_kb(modules))
    await callback.answer("Yangilandi")
