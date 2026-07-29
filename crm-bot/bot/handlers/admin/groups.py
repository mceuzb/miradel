from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Group, User, UserRole, UserStatus
from bot.middlewares.role_check import require_role
from bot.utils.states import GroupCreation

router = Router(name="admin_groups")


@router.message(F.text == "👥 Guruhlar")
@require_role(UserRole.ADMIN)
async def list_groups(message: Message, session: AsyncSession, **kwargs):
    result = await session.execute(select(Group).where(Group.is_archived == False))  # noqa: E712
    groups = result.scalars().all()
    if not groups:
        text = "Hozircha guruhlar yo'q."
    else:
        lines = [f"• {g.name} ({g.subject or '—'})" for g in groups]
        text = "👥 Guruhlar ro'yxati:\n\n" + "\n".join(lines)
    text += "\n\nYangi guruh yaratish uchun /new_group buyrug'ini yuboring."
    await message.answer(text)


@router.message(F.text == "/new_group")
@require_role(UserRole.ADMIN)
async def new_group_start(message: Message, state: FSMContext, **kwargs):
    await message.answer("Yangi guruh nomini kiriting:")
    await state.set_state(GroupCreation.waiting_name)


@router.message(GroupCreation.waiting_name)
async def new_group_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Fan/yo'nalishini kiriting:")
    await state.set_state(GroupCreation.waiting_subject)


@router.message(GroupCreation.waiting_subject)
async def new_group_subject(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    group = Group(name=data["name"], subject=message.text.strip())
    session.add(group)
    await session.commit()
    await state.clear()
    await message.answer(f"✅ '{group.name}' guruhi yaratildi. Endi unga o'qituvchi biriktirishingiz mumkin.")
