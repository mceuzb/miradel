from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from bot.services.module_service import is_module_enabled
from bot.services.referral_service import try_confirm_referral
from bot.services.subscription_service import check_all_required_channels
from bot.utils.states import BroadcastLeadCapture

_BROADCAST_LEAD_STATES = {BroadcastLeadCapture.waiting_name.state, BroadcastLeadCapture.waiting_phone.state}


class SubscriptionCheckMiddleware(BaseMiddleware):
    """7-bo'lim: majburiy obuna moduli yoqilgan bo'lsa, HAR BIR foydalanuvchi -
    hatto hali ro'yxatdan o'tmagan mehmon ham - /start bosgan zahoti tekshiriladi.
    Ro'yxatdan o'tishdan oldin ishlaydi, chunki bu middleware AccessControl'dan
    keyin, lekin har qanday handler'dan oldin ishga tushadi.

    ISTISNO: ommaviy xabar ("kursga qiziqaman") oqimi - bu yerda maqsad tezkor
    lid yig'ish, shuning uchun majburiy obuna talab qilinmaydi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        if event.from_user is None:
            return await handler(event, data)

        # Istisno 1: "📚 Batafsil / Qiziqaman" tugmasining o'zi
        if isinstance(event, CallbackQuery) and event.data and event.data.startswith("broadcast_interest:"):
            return await handler(event, data)

        # Istisno 2: shu tugmadan keyingi ism/telefon so'rash bosqichlari
        state = data.get("state")
        if state is not None:
            current_state = await state.get_state()
            if current_state in _BROADCAST_LEAD_STATES:
                return await handler(event, data)

        # "✅ A'zo bo'ldim" tugmasi bosilganda ham shu yerdan qayta tekshiriladi -
        # agar hali ham a'zo bo'lmasa, pastda yana taklif ko'rsatiladi
        session = data["session"]
        if not await is_module_enabled(session, "mandatory_subscription"):
            return await handler(event, data)

        bot = data["bot"]
        telegram_id = event.from_user.id

        # /start yoki "✅ A'zo bo'ldim" bosilganda - foydalanuvchi HOZIRGINA
        # kanalga a'zo bo'lgan bo'lishi mumkin, shuning uchun eskirgan (5 daqiqagacha)
        # keshlangan natijaga emas, Telegram'dan yangi holatga tayanamiz
        force = (
            (isinstance(event, Message) and event.text and event.text.startswith("/start"))
            or (isinstance(event, CallbackQuery) and event.data == "check_subscription")
        )

        missing = await check_all_required_channels(session, bot, telegram_id, force=force)
        if not missing:
            # Hozir barcha kanallarga a'zo ekani tasdiqlandi - shu daqiqada unga
            # tegishli kutilayotgan referal bo'lsa, konkurs uchun tasdiqlanadi
            await try_confirm_referral(session, telegram_id)
            return await handler(event, data)

        buttons = [
            [InlineKeyboardButton(
                text=f"📢 {ch.channel_title or ch.channel_username}",
                url=ch.invite_link or f"https://t.me/{ch.channel_username.lstrip('@')}",
            )] for ch in missing
        ]
        buttons.append([InlineKeyboardButton(text="✅ A'zo bo'ldim", callback_data="check_subscription")])
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        text = "📢 Botdan foydalanish uchun quyidagi kanal(lar)ga a'zo bo'ling:"

        if isinstance(event, Message):
            await event.answer(text, reply_markup=markup)
        else:
            await event.message.answer(text, reply_markup=markup)
            await event.answer()
        return None
