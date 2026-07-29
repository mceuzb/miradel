from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import get_config
from bot.database.models import Base


def _normalize_url(url: str) -> str:
    """Railway PostgreSQL DATABASE_URL odatda 'postgres://' yoki 'postgresql://'
    ko'rinishida beriladi, lekin asyncpg drayveri uchun 'postgresql+asyncpg://' kerak."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


config = get_config()
engine = create_async_engine(_normalize_url(config.database_url), pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """MVP uchun jadvallarni avtomatik yaratadi. Keyingi bosqichda Alembic
    migratsiyalariga o'tish tavsiya etiladi (production uchun)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
