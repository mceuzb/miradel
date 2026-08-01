import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_config
from bot.database.engine import async_session, init_db
from bot.handlers import admin, channel_membership, common, public, start, student, teacher
from bot.middlewares.access_control import AccessControlMiddleware
from bot.middlewares.db_session import DbSessionMiddleware
from bot.middlewares.subscription_check import SubscriptionCheckMiddleware
from bot.services.module_service import ensure_module_defaults

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    config = get_config()

    await init_db()
    async with async_session() as session:
        await ensure_module_defaults(session)

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware tartibi muhim: avval DB session, keyin access control, keyin obuna tekshiruvi
    dp.message.outer_middleware(DbSessionMiddleware())
    dp.callback_query.outer_middleware(DbSessionMiddleware())
    dp.message.outer_middleware(AccessControlMiddleware())
    dp.callback_query.outer_middleware(AccessControlMiddleware())
    dp.message.outer_middleware(SubscriptionCheckMiddleware())
    dp.callback_query.outer_middleware(SubscriptionCheckMiddleware())

    # chat_member - Telegram foydalanuvchi kanalni tark etganda PUSH qiladigan
    # event, hech qanday skanerlash/polling emas - shunga alohida, faqat DB
    # session middleware kifoya (access control/obuna tekshiruvi kerak emas)
    dp.chat_member.outer_middleware(DbSessionMiddleware())

    dp.include_router(start.router)
    dp.include_router(public.router)
    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(teacher.router)
    dp.include_router(student.router)
    dp.include_router(channel_membership.router)

    logger.info("Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)
    # allowed_updates aniq ko'rsatiladi - shunda Telegram "chat_member" (kanalni
    # tark etish) hodisalarini ham yuborishiga kafolat beriladi
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
