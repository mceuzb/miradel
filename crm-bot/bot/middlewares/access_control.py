from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.database.models import UserStatus
from bot.keyboards.menus import PUBLIC_CALLBACK_DATA, PUBLIC_CALLBACK_PREFIXES, PUBLIC_TEXTS
from bot.services.referral_service import capture_referral
from bot.services.user_service import get_user_by_telegram_id, sync_username
from bot.services.visitor_service import upsert_visitor

PENDING_TEXT = (
    "⏳ Arizangiz ko'rib chiqilmoqda.\n"
    "Admin tasdiqlagandan so'ng botdan to'liq foydalana olasiz."
)
BLOCKED_TEXT = "🚫 Sizning hisobingiz bloklangan. Batafsil ma'lumot uchun administratorga murojaat qiling."
REJECTED_TEXT = "❌ Arizangiz rad etilgan. Qayta murojaat qilish uchun \"🎓 Kursga yozilish\" tugmasini bosing."
REMOVED_TEXT = (
    "😔 Siz o'quvchilar bazasidan topilmadingiz.\n\n"
    "Iltimos, o'qituvchingiz yoki administrator bilan bog'laning."
)


class AccessControlMiddleware(BaseMiddleware):
    """2.4-bo'lim: admin tasdiqlamaguncha shaxsiy panel/funksiyalarga kirish yo'q.
    Lekin PUBLIC_TEXTS (yangiliklar, kurslar jadvali, konkurslar, ro'yxatdan o'tish
    tugmasi) va /start har doim ochiq - ro'yxatdan o'tmagan mehmon foydalanuvchilar
    ham shu ommaviy bo'limlarni ko'ra oladi.

    Bu yerda, blok qilishdan OLDIN, ikkita narsa amalga oshiriladi:
    1. Foydalanuvchi Visitor jadvaliga qayd etiladi (konkurs/referal tizimi
       ro'yxatdan o'tishni talab qilmaydi - shuning uchun HAR BIR odam kuzatiladi).
    2. Referal havola orqali kirilgan bo'lsa (/start ref_<id>) - taklif yozib
       qo'yiladi. Bu SubscriptionCheckMiddleware keyinroq foydalanuvchini
       kanalga a'zo bo'lmagani uchun to'xtatib qo'ysa ham, taklif ma'lumoti
       yo'qolib qolmasligi uchun shart."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, (Message, CallbackQuery)):
            return await handler(event, data)

        session = data["session"]
        telegram_id = event.from_user.id if event.from_user else None

        if telegram_id and event.from_user:
            await upsert_visitor(session, telegram_id, event.from_user.full_name, event.from_user.username)

        if (
            isinstance(event, Message) and event.text and event.text.startswith("/start")
            and telegram_id
        ):
            parts = event.text.split(maxsplit=1)
            if len(parts) == 2 and parts[1].startswith("ref_"):
                try:
                    referrer_telegram_id = int(parts[1].removeprefix("ref_"))
                    await capture_referral(session, telegram_id, referrer_telegram_id)
                except ValueError:
                    pass

        db_user = await get_user_by_telegram_id(session, telegram_id) if telegram_id else None
        if db_user is not None and event.from_user:
            await sync_username(session, db_user, event.from_user.username)
        data["db_user"] = db_user

        # /start va ommaviy (guest) tugmalar - hech qanday tasdiqlashsiz ochiq
        if isinstance(event, Message) and event.text:
            if event.text.startswith("/start") or event.text in PUBLIC_TEXTS:
                return await handler(event, data)

        # MUHIM: inline tugmalar (callback) ham mehmonlar uchun ochiq bo'lishi kerak -
        # aks holda ro'yxatdan o'tmagan foydalanuvchilar "🎲 Qatnashish",
        # "✅ A'zo bo'ldim" kabi tugmalarni bosolmaydi (faqat matn tugmalari
        # emas, callback'lar ham tekshirilishi shart edi)
        if isinstance(event, CallbackQuery) and event.data:
            if event.data in PUBLIC_CALLBACK_DATA or event.data.startswith(PUBLIC_CALLBACK_PREFIXES):
                return await handler(event, data)

        state: FSMContext | None = data.get("state")
        if state is not None and await state.get_state() is not None:
            # Foydalanuvchi biror FSM jarayonida (masalan ro'yxatdan o'tish) - o'tkazamiz
            return await handler(event, data)

        if db_user is None:
            text = "Iltimos, avval /start buyrug'ini bosing."
        elif db_user.status == UserStatus.PENDING:
            text = PENDING_TEXT
        elif db_user.status == UserStatus.BLOCKED:
            text = BLOCKED_TEXT
        elif db_user.status == UserStatus.REJECTED:
            text = REJECTED_TEXT
        elif db_user.status == UserStatus.REMOVED:
            text = REMOVED_TEXT
        else:
            return await handler(event, data)

        if isinstance(event, Message):
            await event.answer(text)
        else:
            await event.answer(text, show_alert=True)
        return None
