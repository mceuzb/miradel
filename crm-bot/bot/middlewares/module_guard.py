import functools
from typing import Any, Awaitable, Callable

from aiogram.types import CallbackQuery, Message

from bot.services.module_service import MODULE_KEYS, is_module_enabled

DISABLED_TEXT = "🔒 Bu bo'lim hozircha faol emas."


def module_guard(module_key: str):
    """3.3-bo'lim: har bir handler ishga tushishidan oldin modul holatini tekshiradi.

    Foydalanish:
        @router.message(F.text == "🎁 Konkurslar")
        @module_guard("contest_module")
        async def show_contests(message: Message, session: AsyncSession, **kwargs):
            ...
    """
    if module_key not in MODULE_KEYS:
        raise ValueError(f"Noma'lum modul kaliti: {module_key}")

    def decorator(func: Callable[..., Awaitable[Any]]):
        @functools.wraps(func)
        async def wrapper(event: Message | CallbackQuery, *args, **kwargs):
            session = kwargs.get("session")
            enabled = await is_module_enabled(session, module_key)
            if not enabled:
                if isinstance(event, Message):
                    await event.answer(DISABLED_TEXT)
                else:
                    await event.answer(DISABLED_TEXT, show_alert=True)
                return None
            return await func(event, *args, **kwargs)
        return wrapper
    return decorator
