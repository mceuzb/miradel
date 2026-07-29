from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User, UserRole
from bot.keyboards.admin_kb import channels_kb
from bot.middlewares.role_check import require_role
from bot.services.channel_service import add_channel, delete_channel, get_all_channels, toggle_channel
from bot.utils.states import ChannelCreation

router = Router(name="admin_channels")


async def _render_channels_message(message: Message, session: AsyncSession):
    channels = await get_all_channels(session)
    if not channels:
        text = (
            "📢 Majburiy kanallar\n\n"
            "Hozircha kanallar qo'shilmagan. Bot majburiy obuna tekshiruvini "
            "faqat ⚙️ Modullar bo'limida 'Majburiy kanalga a'zolik' yoqilgandagina amalga oshiradi."
        )
    else:
        text = "📢 Majburiy kanallar\n\n🟢 - faol, 🔴 - o'chiq. Bosib holatini o'zgartirishingiz mumkin."
    await message.answer(text, reply_markup=channels_kb(channels))


@router.message(F.text == "📢 Majburiy kanallar")
@require_role(UserRole.ADMIN)
async def list_channels(message: Message, session: AsyncSession, **kwargs):
    await _render_channels_message(message, session)


@router.callback_query(F.data == "add_channel")
@require_role(UserRole.ADMIN)
async def add_channel_start(callback: CallbackQuery, state: FSMContext, **kwargs):
    await callback.message.answer(
        "Kanal username'ini kiriting (masalan: mychannel yoki @mychannel).\n\n"
        "⚠️ Diqqat: bot shu kanalda ADMIN sifatida qo'shilgan bo'lishi shart, "
        "aks holda a'zolikni tekshira olmaydi."
    )
    await state.set_state(ChannelCreation.waiting_username)
    await callback.answer()


@router.message(ChannelCreation.waiting_username)
async def add_channel_finish(message: Message, state: FSMContext, session: AsyncSession):
    username = message.text.strip().lstrip("@")
    if not username:
        await message.answer("Noto'g'ri format. Qaytadan kiriting:")
        return
    channel = await add_channel(session, username)
    await state.clear()
    await message.answer(f"✅ @{channel.channel_username} ro'yxatga qo'shildi.")
    await _render_channels_message(message, session)


@router.callback_query(F.data.startswith("toggle_channel:"))
@require_role(UserRole.ADMIN)
async def toggle_channel_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    channel_id = int(callback.data.split(":")[1])
    channel = await toggle_channel(session, channel_id)
    if channel is None:
        await callback.answer("Kanal topilmadi", show_alert=True)
        return
    channels = await get_all_channels(session)
    await callback.message.edit_reply_markup(reply_markup=channels_kb(channels))
    await callback.answer("Yangilandi")


@router.callback_query(F.data.startswith("delete_channel:"))
@require_role(UserRole.ADMIN)
async def delete_channel_callback(callback: CallbackQuery, session: AsyncSession, **kwargs):
    channel_id = int(callback.data.split(":")[1])
    ok = await delete_channel(session, channel_id)
    if not ok:
        await callback.answer("Kanal topilmadi", show_alert=True)
        return
    channels = await get_all_channels(session)
    await callback.message.edit_reply_markup(reply_markup=channels_kb(channels))
    await callback.answer("O'chirildi")
