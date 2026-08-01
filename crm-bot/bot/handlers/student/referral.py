from aiogram import F, Router
from aiogram.types import Message

from bot.database.models import User, UserRole
from bot.middlewares.module_guard import module_guard
from bot.middlewares.role_check import require_role

router = Router(name="student_referral")


@router.message(F.text == "🔗 Do'stlarni taklif qilish")
@require_role(UserRole.STUDENT)
@module_guard("contest_module")
async def my_referral_link(message: Message, db_user: User, **kwargs):
    bot_info = await message.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{db_user.telegram_id}"
    await message.answer(
        "🔗 <b>Sizning shaxsiy taklif havolangiz</b>\n\n"
        f"{link}\n\n"
        "Bu havola orqali kirgan har bir do'stingiz botni ishga tushirib, "
        "barcha majburiy kanallarga a'zo bo'lsagina konkurs reytingingizga "
        "qo'shiladi. Reytingni \"🏆 Reyting\" tugmasidan kuzatib boring!"
    )
