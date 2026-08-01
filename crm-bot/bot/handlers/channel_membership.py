from aiogram import Router
from aiogram.types import ChatMemberUpdated
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.channel_service import is_required_channel
from bot.services.referral_service import revoke_referral

router = Router(name="channel_membership")

# Telegram bot faqat o'zi ADMIN bo'lgan kanal/guruhlar uchun shu eventni oladi -
# hech qanday so'rov/skanerlash kerak emas, Telegram o'zi PUSH qiladi.
_ACTIVE_STATUSES = {"member", "administrator", "creator", "restricted"}
_LEFT_STATUSES = {"left", "kicked"}


@router.chat_member()
async def on_membership_change(event: ChatMemberUpdated, session: AsyncSession):
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    # Faqat "a'zo edi -> chiqib ketdi/chetlatildi" o'tishi bizni qiziqtiradi
    if old_status not in _ACTIVE_STATUSES or new_status not in _LEFT_STATUSES:
        return

    # Faqat bizning majburiy kanallar ro'yxatimizdagi kanaldagi hodisa hisobga olinadi
    if not await is_required_channel(session, event.chat.username):
        return

    left_user = event.new_chat_member.user
    referral = await revoke_referral(session, left_user.id)
    if referral is None:
        return  # bu odam hech kimning tasdiqlangan referali bo'lmagan - hech narsa qilinmaydi

    try:
        await event.bot.send_message(
            referral.referrer_telegram_id,
            f"⚠️ Siz taklif qilgan <b>{left_user.full_name}</b> kanaldan chiqib ketdi.\n"
            "Ball ayirildi - reytingdagi o'rningiz yangilandi.",
        )
    except Exception:
        pass
