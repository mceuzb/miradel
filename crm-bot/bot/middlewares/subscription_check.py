from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from bot.database.models import User
from bot.services.module_service import is_module_enabled
from bot.services.subscription_service import check_all_required_channels


class SubscriptionCheckMiddleware(BaseMiddleware):
    """7-bo'lim: majburiy obuna moduli yoqilgan bo'lsa, har bir xabarda tekshiradi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        db_user: User | None = data.get("db_user")
        if db_user is None:
            # Ro'yxatdan o'tmagan yoki tasdiqlanmagan foydalanuvchi - access_control allaqachon boshqargan
            return await handler(event, data)

        state: FSMContext | None = data.get("state")
        if state is not None and await state.get_state() is not None:
            return await handler(event, data)

        # "✅ A'zo bo'ldim" tugmasi bosilganda ham shu yerdan qayta tekshiriladi
        session = data["session"]
        if not await is_module_enabled(session, "mandatory_subscription"):
            return await handler(event, data)

        bot = data["bot"]
        missing = await check_all_required_channels(session, bot, db_user.telegram_id)
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
