from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_config
from bot.database.models import User
from bot.keyboards.menus import ALPINO_BUTTON_TEXT, menu_for_role
from bot.services.alpino_access import alpino_access_allowed

router = Router(name="common")


@router.message(F.text == ALPINO_BUTTON_TEXT)
async def alpino_open_webapp(message: Message, db_user: User | None, session: AsyncSession, **kwargs):
    """"⛰️ Alpino" matn tugmasi bosilganda inline web_app tugmasi bilan
    alohida xabar yuboradi. MUHIM: Telegram faqat SHU yo'l bilan (inline
    tugma / Menu Button / to'g'ridan-to'g'ri havola) ochilgan Mini App'ga
    haqiqiy (bo'sh bo'lmagan) initData beradi - klaviatura (pastki)
    tugmasida initData har doim bo'sh keladi (Telegram'ning rasmiy
    hujjatiga ko'ra), shuning uchun bu bosqich shart."""
    if db_user is None:
        return
    url = get_config().get_alpino_url()
    if not url or not await alpino_access_allowed(session, db_user.role):
        await message.answer("Alpino hozircha faol emas.")
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⛰️ Alpino'ni ochish", web_app=WebAppInfo(url=url))]
    ])
    await message.answer("Alpino mini-ilovasini ochish uchun tugmani bosing:", reply_markup=kb)


@router.callback_query(F.data == "check_subscription")
async def recheck_subscription(callback: CallbackQuery, db_user: User | None, session: AsyncSession, **kwargs):
    # Bu handlerga yetib kelgan bo'lsa - SubscriptionCheckMiddleware allaqachon
    # foydalanuvchi barcha kanallarga a'zo ekanini tasdiqlagan
    await callback.message.delete()
    if db_user:
        await callback.message.answer(
            "✅ Rahmat! Botdan foydalanishingiz mumkin.",
            reply_markup=await menu_for_role(session, db_user.role),
        )
    await callback.answer()
