import functools
from typing import Any, Awaitable, Callable

from aiogram.types import CallbackQuery, Message

from bot.database.models import User, UserRole

NO_ACCESS_TEXT = "⛔️ Sizda bu buyruq uchun huquq yo'q."


def require_role(*roles: UserRole):
    """11-bo'lim: har bir buyruq uchun rol tekshiruvi (middleware/dekorator).

    Foydalanish:
        @router.message(Command("panel"))
        @require_role(UserRole.ADMIN)
        async def admin_panel(message: Message, db_user: User, **kwargs):
            ...
    """
    def decorator(func: Callable[..., Awaitable[Any]]):
        @functools.wraps(func)
        async def wrapper(event: Message | CallbackQuery, *args, **kwargs):
            db_user: User | None = kwargs.get("db_user")
            if db_user is None or db_user.role not in roles:
                if isinstance(event, Message):
                    await event.answer(NO_ACCESS_TEXT)
                else:
                    await event.answer(NO_ACCESS_TEXT, show_alert=True)
                return None
            return await func(event, *args, **kwargs)
        return wrapper
    return decorator
