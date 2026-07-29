from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from bot.services.module_service import is_module_enabled
from bot.services.subscription_service import check_all_required_channels


class SubscriptionCheckMiddleware(BaseMiddleware):
    """7-bo'lim: majburiy obuna moduli yoqilgan bo'lsa, HAR BIR foydalanuvchi -
    hatto hali ro'yxatdan o'tmagan mehmon ham - /start bosgan zahoti tekshiriladi.
    Ro'yxatdan o'tishdan oldin ishlaydi, chunki bu middleware AccessControl'dan
    keyin, lekin har qanday handler'dan oldin ishga tushadi."""

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

        # "✅ A'zo bo'ldim" tugmasi bosilganda ham shu yerdan qayta tekshiriladi -
        # agar hali ham a'zo bo'lmasa, pastda yana taklif ko'rsatiladi
        session = data["session"]
        if not await is_module_enabled(session, "mandatory_subscription"):
            return await handler(event, data)

        bot = data["bot"]
        telegram_id = event.from_user.id
        missing = await check_all_required_channels(session, bot, telegram_id)
        if not missing:
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
