from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.database.models import UserStatus
from bot.services.user_service import get_user_by_telegram_id

PENDING_TEXT = (
    "⏳ Arizangiz ko'rib chiqilmoqda.\n"
    "Admin tasdiqlagandan so'ng botdan to'liq foydalana olasiz."
)
BLOCKED_TEXT = "🚫 Sizning hisobingiz bloklangan. Batafsil ma'lumot uchun administratorga murojaat qiling."
REJECTED_TEXT = "❌ Arizangiz rad etilgan. Qayta murojaat qilish uchun /start bosing."


class AccessControlMiddleware(BaseMiddleware):
    """2.4-bo'lim: admin tasdiqlamaguncha hech qanday panel/funksiyaga kirish yo'q.
    Ro'yxatdan o'tish FSM jarayoni davomida (state faol bo'lganda) bloklanmaydi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        # /start har doim ochiq - registratsiya shu yerdan boshlanadi
        if isinstance(event, Message) and event.text and event.text.startswith("/start"):
            return await handler(event, data)

        state: FSMContext | None = data.get("state")
        if state is not None and await state.get_state() is not None:
            # Foydalanuvchi biror FSM jarayonida (masalan ro'yxatdan o'tish) - o'tkazamiz
            return await handler(event, data)

        session = data["session"]
        telegram_id = event.from_user.id if event.from_user else None
        db_user = await get_user_by_telegram_id(session, telegram_id) if telegram_id else None
        data["db_user"] = db_user

        if db_user is None:
            text = "Iltimos, avval /start buyrug'ini bosing."
        elif db_user.status == UserStatus.PENDING:
            text = PENDING_TEXT
        elif db_user.status == UserStatus.BLOCKED:
            text = BLOCKED_TEXT
        elif db_user.status == UserStatus.REJECTED:
            text = REJECTED_TEXT
        else:
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(text)
        else:
            await event.answer(text, show_alert=True)
        return None
