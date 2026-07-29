from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Group, User, UserRole
from bot.middlewares.role_check import require_role

router = Router(name="teacher_groups")


@router.message(F.text == "👥 Guruhlarim")
@require_role(UserRole.TEACHER)
async def my_groups(message: Message, session: AsyncSession, db_user: User, **kwargs):
    result = await session.execute(select(Group).where(Group.teacher_id == db_user.id))
    groups = result.scalars().all()
    if not groups:
        await message.answer("Sizga hali guruh biriktirilmagan.")
        return
    lines = [f"• {g.name} ({g.subject or '—'})" for g in groups]
    await message.answer("👥 Sizning guruhlaringiz:\n\n" + "\n".join(lines))
