from aiogram import Router
from aiogram.types import ChatMemberUpdated
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.channel_service import is_required_channel
from bot.services.referral_service import restore_referral, revoke_referral
from bot.services.subscription_service import check_all_required_channels

router = Router(name="channel_membership")

# Telegram bot faqat o'zi ADMIN bo'lgan kanal/guruhlar uchun shu eventni oladi -
# hech qanday so'rov/skanerlash kerak emas, Telegram o'zi PUSH qiladi.
_ACTIVE_STATUSES = {"member", "administrator", "creator", "restricted"}
_LEFT_STATUSES = {"left", "kicked"}


@router.chat_member()
async def on_membership_change(event: ChatMemberUpdated, session: AsyncSession):
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    if old_status == new_status:
        return
    if not await is_required_channel(session, event.chat.username):
        return

    changed_user = event.new_chat_member.user

    # HOLAT 1: a'zo edi -> chiqib ketdi/chetlatildi -> ball ayiriladi
    if old_status in _ACTIVE_STATUSES and new_status in _LEFT_STATUSES:
        referral = await revoke_referral(session, changed_user.id)
        if referral is None:
            return
        try:
            await event.bot.send_message(
                referral.referrer_telegram_id,
                f"⚠️ Siz taklif qilgan <b>{changed_user.full_name}</b> kanaldan chiqib ketdi.\n"
                "Ball ayirildi - reytingdagi o'rningiz yangilandi.",
            )
        except Exception:
            pass
        return

    # HOLAT 2: chiqib ketgan edi -> qaytadan a'zo bo'ldi -> ball qaytariladi
    # (lekin FAQAT barcha majburiy kanallarga to'liq a'zo bo'lsa - agar boshqa
    # bir majburiy kanalga hali a'zo bo'lmasa, ball hali qaytarilmaydi)
    if old_status in _LEFT_STATUSES and new_status in _ACTIVE_STATUSES:
        missing = await check_all_required_channels(session, event.bot, changed_user.id, force=True)
        if missing:
            return  # boshqa majburiy kanal(lar)ga hali a'zo emas

        referral = await restore_referral(session, changed_user.id)
        if referral is None:
            return
        try:
            await event.bot.send_message(
                referral.referrer_telegram_id,
                f"✅ Siz taklif qilgan <b>{changed_user.full_name}</b> kanalga qaytib a'zo bo'ldi.\n"
                "Ball qaytarildi!",
            )
        except Exception:
            pass
